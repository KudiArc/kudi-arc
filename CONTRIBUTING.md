# Contributing to Kudi Arc

Thank you for your interest in contributing to Kudi Arc — financial infrastructure for Africa. We welcome contributions from developers across the continent and beyond.

---

## Ways to Contribute

| Type | Examples |
|------|---------|
| 🐛 Bug reports | API errors, frontend issues, incorrect FX rates |
| ✨ Feature requests | New country corridors, UI improvements, new endpoints |
| 🔐 Security reports | Smart contract vulnerabilities, API security issues |
| 📝 Documentation | Improving clarity, fixing typos, adding examples |
| 🧪 Testing | Writing tests, testing on Arc Testnet, edge case coverage |
| 🌍 Translations | Localising the UI for African languages (Hausa, Swahili, French) |

---

## Before You Start

1. **Check existing issues** at [github.com/KudiArc/kudi-arc/issues](https://github.com/KudiArc/kudi-arc/issues) — your idea may already be tracked.
2. **For significant changes**, open an issue first to discuss the approach before writing code.
3. **For security vulnerabilities**, do NOT open a public issue — see [SECURITY.md](./SECURITY.md).

---

## Development Setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/kudi-arc.git
cd kudi-arc

# 2. Add the upstream remote
git remote add upstream https://github.com/KudiArc/kudi-arc.git

# 3. Set up the Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Fill in your Arc Testnet RPC, API keys, etc.

# 5. Initialise the database
python3 db.py

# 6. Run the backend
python3 app.py
# API available at http://localhost:5000

# 7. Open the frontend
# Open index.html, send.html, or yield.html in your browser
# (or serve with: python3 -m http.server 8080)
```

---

## Making a Contribution

```bash
# 1. Sync your fork with upstream
git fetch upstream
git checkout main
git merge upstream/main

# 2. Create a feature branch
git checkout -b feature/your-feature-name
# Use a descriptive name: feature/add-ethiopia-corridor, fix/rate-display-bug

# 3. Make your changes
# ... write code, test it, update docs if needed ...

# 4. Commit with a clear message
git add .
git commit -m "feat: add Ethiopia (ETB) payout corridor via Flutterwave"
# See commit message format below

# 5. Push to your fork
git push origin feature/your-feature-name

# 6. Open a Pull Request on GitHub
# Go to github.com/KudiArc/kudi-arc and click "Compare & pull request"
```

---

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

[optional body]
[optional footer]
```

| Type | When to use |
|------|------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `test` | Adding or updating tests |
| `chore` | Build scripts, dependencies, tooling |
| `security` | Security fix or hardening |

**Examples:**
```
feat: add Uganda UGX corridor via Flutterwave
fix: correct NGN rate display on send.html
docs: add cURL examples to API.md
security: add signature replay protection to /api/send/payout
```

---

## Pull Request Guidelines

A good PR:

- [ ] Has a clear title describing what it does
- [ ] References the related issue (e.g. `Closes #42`)
- [ ] Includes a short description of the approach taken
- [ ] Has been tested on Arc Testnet (for contract or API changes)
- [ ] Updates relevant documentation (`API.md`, `ARCHITECTURE.md`, etc.) if the change affects them
- [ ] Does not introduce new lint errors or break existing functionality

**PR template:**

```markdown
## What does this PR do?
Brief description of the change.

## Related issue
Closes #___

## How was it tested?
- [ ] Tested locally
- [ ] Tested on Arc Testnet
- [ ] Existing functionality still works

## Notes for reviewer
Any context that would help the review.
```

---

## Areas Where Help Is Most Needed

### 🌍 Country Corridor Expansion
Adding new African countries requires: FX rate config, partner API integration, bank list (if applicable), and frontend country entry. Good first contribution.

**Reference:** See how Nigeria is implemented in `app.py` and replicate for Ethiopia, Egypt, or Mozambique.

### 🧪 Test Coverage
The backend currently has no automated test suite. Writing `pytest` tests for the Flask API endpoints would be a high-value contribution.

```bash
pip install pytest pytest-flask
# Tests should go in: tests/test_api.py, tests/test_db.py
```

### 📱 Mobile UX Improvements
The frontend HTML files work on mobile but weren't built mobile-first. CSS improvements, better touch targets, and PWA manifest enhancements are welcome.

### 🌐 Localisation
The UI is English-only. Adding language support for Hausa (Northern Nigeria), Swahili (East Africa), or French (West Africa) would significantly expand reach.

---

## Code Style

**Python (backend):**
- Follow PEP 8
- Use descriptive variable names — avoid single-letter variables outside loops
- Add docstrings to all new functions
- Keep route handlers thin — move logic to helper functions

**JavaScript (frontend):**
- Use `const` and `let`, never `var`
- Use `async/await` over `.then()` chains
- Add `try/catch` around all wallet and API calls
- Log errors to console with context: `console.error('swap failed:', err)`

**Solidity (contracts):**
- Follow the existing style in `KudiSwapV2.sol`
- Add NatSpec comments to all public functions
- Test with Foundry (`forge test`) before submitting

---

## Community

- **Discord:** [discord.gg/kudiarc](https://discord.gg/nEJfqrAsqc)
- **Twitter/X:** [@KudiArc](https://twitter.com/KudiArc)
- **GitHub Issues:** For bugs and feature requests

We are especially interested in connecting with developers from Nigeria, Kenya, Ghana, and other African countries who understand the local financial landscape.

---

*Built in Africa 🌍 — Kudi means money. Arc means infrastructure.*
