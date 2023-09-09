import sys
sys.path.insert(0, '..')

from datetime import datetime
from flask import Flask, request, jsonify
from bond import Bond
from curve import Curve
from oas import OASModel
from yieldcalculator import YieldCalculator

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route('/bond', methods=['GET'])
def bond():
    cusip = request.args.get('cusip')
    if cusip:
        bond = Bond.load_by_cusip(cusip, csv='../data/bonds.csv')
        return jsonify(bond.to_json())
    return jsonify([bond.to_json() for bond in Bond.load_all_bonds('../data/bonds.csv')])
    
@app.route('/pricing', methods=['GET'])
def pricing():
    cusip = request.args.get('cusip')
    price = request.args.get('price')
    valueDate = request.args.get('value_date')
    try:
        valueDate = datetime.strptime(valueDate, '%Y%m%d').date()
    except:
        return f"value_date should be in %Y%m%d format"
    try:
        price = float(price)
    except:
        return f"price should be a float number"
    
    bond = Bond.load_by_cusip(cusip, csv='../data/bonds.csv')
    if not bond:
        return f"Bond not found with cusip {cusip}"
    
    spot_curve = Curve(valueDate)
    spot_curve.load_from_csv('../data/treasuryspotcurve.csv')
    if not spot_curve:
        return f"Cannot find spot curve for {valueDate}"
    
    par_curve = Curve(valueDate)
    par_curve.load_from_csv('../data/treasuryparcurve.csv')
    if not par_curve:
        return f"Cannot find par curve for {valueDate}"

    bond.calculate_coupon_schedule()
    ytm = YieldCalculator.get_ytm(bond, bond._market_price, valueDate)
    ytc = YieldCalculator.get_ytc(bond, bond._market_price, valueDate)
    ytw = YieldCalculator.get_ytw(bond, bond._market_price, valueDate)
    tenor, trsy_yield = YieldCalculator.get_yield_spread(bond, ytm, par_curve, interpolate=False)
    spread = request.args.get('oas') or bond.Cpn
    spread = float(spread)
    oas = OASModel().Calculate_OAS(bond, spot_curve, valueDate, price, spread)
    print(bond, bond._market_price, ytm, ytc, ytw[0], tenor, trsy_yield, ytm - trsy_yield)
    result = {'CUSIP': bond.CUSIP,
              'Coupon': bond.Cpn,
              'Maturity': bond.Maturity.strftime('%m/%d/%Y'),
              'ValueDate': valueDate.strftime('%m/%d/%Y'),
              'Price': price,
              'ytm': ytm,
              'ytc': ytc,
              'ytw': ytw[0],
              'ytw_date': ytw[1].strftime('%m/%d/%Y'),
              'ytm to treasury spread': ytm - trsy_yield,
              'jtd': bond.get_jtd_risk(),
              'OAS': oas}
    return jsonify(result)
