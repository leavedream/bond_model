from datetime import datetime, date, timedelta
from coupon import Coupon
from dateutil.relativedelta import relativedelta
import utilities
import pandas as pd
import json

class Bond():
    def __init__(self, 
                 cusip: str=None,
                 maturity: date=None,
                 ticker: str=None,
                 issue_date: date=None,
                 cpn:float=None,
                 cpn_type: str=None,
                 cpn_freq: int=None,
                 issued_amt: float=None,
                 next_call_date: date=None,
                 next_call_price: float=None,
                 rating: str=None,
                 maturity_type: str=None,
                 announce_date: date=None,
                 ccy:str=None,
                 effective_date: date=None,
                 first_cpn_date: date=None,
                 face_value: float=100,
                 day_count: str=None,
                 redemption: float=100,
                 price: float=.0
                 ) -> None:
        self.CUSIP = cusip
        self.Maturity = maturity
        self.Ticker = ticker
        self.IssueDate = issue_date
        self.Cpn = cpn
        self.CouponType = cpn_type
        self.CouponFreq = cpn_freq
        self.IssuedAmount = issued_amt
        self.NextCallDate = next_call_date
        self.NextCallPrice = next_call_price
        self.CompositeRating = rating
        self.MaturityType = maturity_type
        self.Announce = announce_date
        self.EffectiveDate = effective_date
        self.FirstCouponDate = first_cpn_date
        self.Currency = ccy
        self.FaceValue = face_value
        self.Redemption = redemption
        self.DayCount = day_count or "ACT/360"
        self._coupon_schedule = None
        self._numCoupon = 0
        self._market_price = price
        self._recovery_rate = 0.75
        # caching calculation results
        self._ytm = None
        self._ytc = None
        self._ytw = None
        self._oas = None

        # constants
        self._YEAR_STEPS = 100
        self._IR_VOL = 0.3
        self._IR_MEANREVERSION = 0.1

    def __str__(self):
        return f"{self.CUSIP} {self.Cpn * 100} {self.Maturity.strftime('%m/%d/%Y')}"

    def calculate_coupon_schedule(self) -> None:
        ''' Construct coupon schedules
        '''
        self._coupon_schedule = []
        self._numCoupon = 0
        cpn = Coupon(self.EffectiveDate, self.Cpn)
        self._coupon_schedule.append(cpn)

        curr_date = self.Maturity
        while curr_date > self.EffectiveDate:
            self.FirstCouponDate = curr_date
            curr_date = curr_date - relativedelta(months=12 / self.CouponFreq)

        curr_date = self.FirstCouponDate
        max_date = self.Maturity + timedelta(days=-15)
        while curr_date < max_date:
            self._numCoupon += 1
            self._coupon_schedule[-1].couponTenor = utilities.calcYearFrac(self._coupon_schedule[-1].couponDate, curr_date, self.DayCount)
            self._coupon_schedule.append(Coupon(curr_date, self.Cpn))
            curr_date = curr_date + relativedelta(months=12/self.CouponFreq)

        self._numCoupon += 1
        self._coupon_schedule[-1].couponTenor = utilities.calcYearFrac(self._coupon_schedule[-1].couponDate, self.Maturity, self.DayCount)
        self._coupon_schedule.append(Coupon(self.Maturity, self.Cpn))


    def _get_next_date_idx(self, valueDate: date) -> int:
        idx = 0
        while idx <= self._numCoupon and self._coupon_schedule[idx].couponDate < valueDate:
            idx += 1
        return idx

    def get_jtd_risk(self) -> float:
        
        return self._market_price - self._recovery_rate * 100

    @classmethod
    def load_by_cusip(cls, cusip, csv=None):
        csv = csv or './data/bonds.csv'
        df = pd.read_csv(csv)
        df = df[df['CUSIP']==cusip]
        if df.empty:
            print(f'Bond with cusip {cusip} not found')
            return None

        return cls._from_csv_row(df.iloc[0])

    @classmethod
    def _from_csv_row(cls, row):
        return cls(cusip=row['CUSIP'],
                  maturity=datetime.strptime(row['Maturity'], '%m/%d/%Y').date(),
                  ticker=row['Ticker'],
                  issue_date=datetime.strptime(row['Issue Date'], '%m/%d/%Y').date(),
                  cpn=float(row['Cpn']) / 100,
                  cpn_type=row['Coupon Type'],
                  cpn_freq=int(row['Coupon Freq']),
                  issued_amt=float(row['Issued Amount']),
                  next_call_date=datetime.strptime(row['Next Call Date'], '%m/%d/%Y').date() if '#N/A' not in row['Next Call Date'] else None,
                  next_call_price=100,
                  rating=row['Composite Rating'], 
                  maturity_type=row['Maturity Type'],
                  announce_date=datetime.strptime(row['Announce'], '%m/%d/%Y').date(),
                  ccy=row['Currency'],
                  effective_date=datetime.strptime(row['Issue Date'], '%m/%d/%Y').date(),
                  first_cpn_date=None,
                  face_value=100,
                  day_count='ACT/360',
                  redemption=100,
                  price=row['Ask Price']
            )

    @classmethod
    def load_all_bonds(cls, csv=None):
        csv = csv or './data/bonds.csv'
        df = pd.read_csv(csv)
        bonds = [cls._from_csv_row(row) for _, row in df.iterrows()]
        return bonds

    def to_json(self):
        return {'CUSIP': self.CUSIP,
                'Maturity': self.Maturity.strftime('%m/%d/%Y'),
                'Ticker': self.Ticker,
                'Issue Date': self.IssueDate.strftime('%m/%d/%Y'),
                'Cpn': self.Cpn * 100,
                'Coupon Type': self.CouponType,
                'Coupon Freq': self.CouponFreq,
                'Issued Amount': self.IssuedAmount,
                'Next Call Date': self.NextCallDate.strftime('%m/%d/%Y') if self.NextCallDate else None,
                'Next Call Price': self.NextCallPrice,
                'Composite Rating': self.CompositeRating, 
                'Maturity Type': self.MaturityType,
                'Announce': self.Announce.strftime('%m/%d/%Y'),
                'Currency': self.Currency,
                'Recovery': self._recovery_rate,
                'Ask Price': self._market_price}
    
    @classmethod
    def from_json(cls, json_data):
        return cls(cusip=json_data.get('CUSIP'),
                  maturity=datetime.strptime(json_data.get('Maturity'), '%m/%d/%Y').date(),
                  ticker=json_data.get('Ticker'),
                  issue_date=datetime.strptime(json_data('Issue Date'), '%m/%d/%Y').date(),
                  cpn=float(json_data['Cpn']) / 100,
                  cpn_type=json_data.get('Coupon Type'),
                  cpn_freq=int(json_data.get('Coupon Freq')),
                  issued_amt=float(json_data.get('Issued Amount')),
                  next_call_date=datetime.strptime(json_data.get('Next Call Date'), '%m/%d/%Y').date() if '#N/A' not in json_data.get('Next Call Date') else None,
                  next_call_price=float(json_data.get('Next Call Price')),
                  rating=['Composite Rating'], 
                  maturity_type=json_data['Maturity Type'],
                  announce_date=datetime.strptime(json_data.get('Announce'), '%m/%d/%Y').date(),
                  ccy=json_data.get('Currency'),
                  effective_date=datetime.strptime(json_data.get('Issue Date'), '%m/%d/%Y').date(),
                  first_cpn_date=None,
                  face_value=100,
                  day_count='ACT/360',
                  redemption=100,
                  price=json_data.get('Ask Price')
            )
