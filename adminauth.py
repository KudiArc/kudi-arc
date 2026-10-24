"""Owner-only admin authentication.

Each admin request carries a single-use nonce and a signature over the exact
request (method, path, body hash, nonce, expiry). Fails closed when
OWNER_ADDRESS is not configured.
"""
import hashlib, logging, secrets, time
from functools import wraps
from flask import jsonify, request
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

import db

log = logging.getLogger("kudi-arc.admin")

NONCE_TTL = 120
MAX_OPEN_NONCES = 50


def build_message(domain, chain_id, method, path, body_hash, nonce, expires):
    return (f"KudiArc admin request\nDomain: {domain}\nChain: {chain_id}\n"
            f"Method: {method}\nPath: {path}\nBody: {body_hash}\n"
            f"Nonce: {nonce}\nExpires: {expires}")


class AdminAuth:
    def __init__(self, owner_address, chain_id, domain="kudiarc.xyz"):
        owner = (owner_address or "").strip()
        self.owner = owner.lower() if Web3.is_address(owner) else ""
        self.chain_id, self.domain = chain_id, domain

    @property
    def enabled(self):
        return bool(self.owner)

    def _deny(self, reason, status=401):
        log.warning(f"admin auth denied: {reason}")
        return jsonify({"error": "Unauthorized", "code": "unauthorized"}), status

    def challenge(self):
        if not self.enabled:
            return jsonify({"error": "Admin is not configured", "code": "admin_disabled"}), 503
        now = int(time.time())
        if db.open_admin_nonce_count(now) >= MAX_OPEN_NONCES:
            return jsonify({"error": "Too many pending requests", "code": "rate_limited"}), 429
        nonce, expires = secrets.token_hex(16), now + NONCE_TTL
        db.create_admin_nonce(nonce, expires)
        return jsonify({"nonce": nonce, "expires_at": expires,
                        "domain": self.domain, "chain_id": self.chain_id})

    def required(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not self.enabled:
                return jsonify({"error": "Admin is not configured", "code": "admin_disabled"}), 503
            nonce = request.headers.get("X-Admin-Nonce", "")
            sig = request.headers.get("X-Admin-Signature", "")
            row = db.get_admin_nonce(nonce) if nonce else None
            if not row or row["used"] or row["expires_at"] < int(time.time()):
                return self._deny("missing, used or expired nonce")
            qs = request.query_string.decode()
            path = request.path + (f"?{qs}" if qs else "")
            body_hash = hashlib.sha256(request.get_data()).hexdigest()
            msg = build_message(self.domain, self.chain_id, request.method, path,
                                body_hash, nonce, row["expires_at"])
            try:
                signer = Account.recover_message(encode_defunct(text=msg), signature=sig)
            except Exception:
                return self._deny("unreadable signature")
            if signer.lower() != self.owner:
                return self._deny("signer is not the owner")
            if not db.consume_admin_nonce(nonce):          # single use, atomic
                return self._deny("nonce already used")
            return fn(*args, **kwargs)
        return wrapper
