from bond import Bond
from curve import Curve
from datetime import date
from dateutil.relativedelta import relativedelta
import utilities

class YieldCalculator():
    ''' collection of static method calculate yields for the given bond, price and value date
    '''
    @staticmethod
    def get_clean_price_from_yield(bond: Bond, yld: float, valueDate:date) -> float:
        ''' Calculate price given yield
        '''
        if valueDate > bond.Maturity:
            return 0.0
        
        i = bond._get_next_date_idx(valueDate)
        # Accrued Interest
        if i != 0 and i < bond._numCoupon+1:
            accruedInt = bond.FaceValue * bond._coupon_schedule[i-1].couponRate * utilities.calcYearFrac(bond._coupon_schedule[i-1].couponDate, valueDate, bond.DayCount)

        # Bond price
        dirtyPrice  = 0.0

        # Redemption Value
        if i <= bond._numCoupon:
            t = (bond._coupon_schedule[bond._numCoupon].couponDate - valueDate).days / 365.25
            if t>=0:
                dirtyPrice += bond.Redemption * pow(1.0 + yld/bond.CouponFreq, -1 * t * bond.CouponFreq)

        # Coupons
        i = max(i, 1)
        while i <= bond._numCoupon:
            t = (bond._coupon_schedule[i].couponDate - valueDate).days / 365.25
            if t >= 0:
                amt = bond.FaceValue * bond._coupon_schedule[i-1].couponRate * bond._coupon_schedule[i-1].couponTenor
                dirtyPrice += amt * pow(1.0 + yld / bond.CouponFreq, -1 * t * bond.CouponFreq)
            i += 1

        return dirtyPrice - accruedInt

    @staticmethod
    def _price_from_yield_bisec_func(yld: float, **kwargs) -> float:
        bond, price, valueDate = kwargs['bond'], kwargs['price'], kwargs['valueDate']
        return YieldCalculator.get_clean_price_from_yield(bond, yld, valueDate) - price

    @staticmethod
    def get_ytm(bond: Bond, price: float, valueDate:date=None) -> float: 
        ''' Return: 
            Yield to maturity given price
            Parameters:
            bond: the Bond
            price: float, market price
            valueDate: date
        '''
        valueDate = valueDate or date.today()
        kwargs = {'price': price, 'valueDate': valueDate, 'bond': bond}
        return utilities.bisectSolve(YieldCalculator._price_from_yield_bisec_func, **kwargs)

    @staticmethod
    def get_ytc(bond: Bond, price: float, valueDate:date=None) -> float:
        ''' Return:
            Yield to Next Call if Callable, None otherwise
        '''
        if not bond.NextCallDate:
            return None
        valueDate = valueDate or date.today()
        bond.Maturity = bond.NextCallDate
        bond.Redemption = bond.NextCallPrice
        return YieldCalculator.get_ytm(bond, price, valueDate)

    @staticmethod
    def get_ytw(bond: Bond, price: float, valueDate: date=None) -> tuple:
        ''' starting from the first next call date to maturity date, calculate the worst yield
            This function assumes there's only one call schedule from next call date to maturity
            Return:
            tuple, first element is ytw, second element is date for the yet
        '''
        ytw, ytw_date = YieldCalculator.get_ytm(bond, price, valueDate), bond.Maturity
        if not bond.NextCallDate:
            return (ytw, ytw_date)
        valueDate = valueDate or date.today()
        callDate = bond.NextCallDate
        while callDate <= bond.Maturity:
            bond.Maturity = callDate
            bond.Redemption = bond.NextCallPrice
            new_yield = YieldCalculator.get_ytm(bond, price, valueDate)
            if new_yield < ytw:
                ytw = new_yield
                ytw_date = callable
            callDate = callDate + relativedelta(days=7)
        return (ytw, ytw_date)
    
    @staticmethod
    def get_yield_spread(bond: Bond, ytm: float, treasury_curve: Curve, interpolate=False):
        ''' Find the treasury rate in the curve by Maturity, linear interpolation when interpolate=True, 
            use the closet one rate otherwise
            Return:
              The spread between YTM and treasury yield.
        '''
        result = [None, None]
        treasury_curve.getTheRate(bond.Maturity, interpolate=interpolate, out=result)
        return result
