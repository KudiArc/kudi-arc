def test_default_floor_does_not_change_country_fee(make_env):
    e = make_env(); e.fee_floor = 0.3
    assert e.quote()["fee"] == "0.16"                      # NG fee 0.8% is already above 0.3%


def test_floor_raises_fee_when_higher_than_country_fee(make_env):
    e = make_env(); e.fee_floor = 2.0                       # NG 0.8% -> 2%
    q = e.quote()
    assert q["fee"] == "0.4" and q["fee_pct"] == 2.0 and q["payout_amount"] == "29400.00"


def test_floor_never_lowers_fee(make_env):
    e = make_env(); e.fee_floor = 0.1
    assert e.quote(country_code="KE", method="mobile_money", phone="+254700000000",
                   account_number="", bank_code="")["fee"] == "0.7"      # KE 3.5% stays


def test_bad_floor_values_are_ignored(make_env):
    for v in (None, -5, 0):
        e = make_env(); e.fee_floor = v
        assert e.quote()["fee"] == "0.16"
