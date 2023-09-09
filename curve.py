from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
from utilities import toDateNumber

class Curve():
    ''' Curve representation
    '''
    def __init__(self, valueDate:date) -> None:
        self._valueDate = valueDate
        self._valueDateNum = toDateNumber(valueDate)
        self._numRate = 0
        self._compoundFreq = 2  # semi
        self._ir_vol = 0.2
        self._mean_reversion = 0.05
        self._data = []
    
    def __str__(self) -> str:
        rtn = [f"{self._valueDate.strftime('%Y-%m-%d')}"]
        for d in self._data:
            rtn.append(f"{d[0].strftime('%Y-%m-%d')}\t{d[1]}")
        return "\n".join(rtn)

    def append_data(self, rate: float, rate_date: date) -> None:
        self._data.append((rate_date, rate, toDateNumber(rate_date)))
    
    def get_curve_data(self) -> None:
        return self._data
    
    def download_curve(self) -> None:
        yearmonth = self._valueDate.strftime('%Y%m')
        url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv"
               f"/all/{yearmonth}?type=daily_treasury_yield_curve&field_tdr_date_value_month={yearmonth}&page&_format=csv")
        df = pd.read_csv(url)
        df_day = df[df['Date']==self._valueDate.strftime('%m/%d/%Y')]
        df_day = df_day.reset_index(drop=True)
        for col in df_day.columns:
            if col == 'Date':
                continue
            if 'Mo' in col:
                _date = self._valueDate + relativedelta(months=int(col.split(' ')[0]))
            elif 'Yr' in col:
                _date = self._valueDate + relativedelta(years=int(col.split(' ')[0]))
            _rate = float(df_day.loc[0, col]) / 100
            self.append_data(_rate, _date)
        self._numRate = len(self._data)

    def getTheRate(self, value_date: [date, float], interpolate=False, out=None):
        ''' Get the rate for the given date in the curve 
            when interpolate = True: do linear interpolation
            otherwise, find the cloest rate
            Return:
              rate
        '''
        if self._numRate <= 0:
            return -1
        if isinstance(value_date, date):
            value_date = toDateNumber(value_date)

        for i in range(self._numRate):
            if value_date <= self._data[i][2]:
                if i==0:
                    if out:
                        out[0], out[1] = self._data[i][0], self._data[i][1]
                    return self._data[i][1]

                prev_rate = self._data[i-1][1]
                curr_rate = self._data[i][1]
                if interpolate:
                    period = self._data[i][2] - self._data[i-1][2]
                    dt = value_date - self._data[i-1][2]
                    the_rate = prev_rate + (curr_rate - prev_rate) * dt / period
                    if out:
                        out[0], out[1] = value_date, the_rate
                    return the_rate
                else:
                    if (value_date - self._data[i-1][2] < self._data[i][2] -value_date):
                        if out:
                            out[0], out[1] = self._data[i-1][0], self._data[i-1][1]
                        return self._data[i-1][1]
                    else:
                        if out:
                            out[0], out[1] = self._data[i][0], self._data[i][1]
                        return self._data[i][1]
        if out:
            out[0], out[1] = self._data[-1][0], self._data[-1][1]
        return self._data[-1][1]

    def load_from_csv(self, csv: str):
        ''' load from csv file '''
        self._data = []
        df = pd.read_csv(csv)
        if df.empty:
            raise Exception(f"Failed to load curve from file {csv}")
        df['Date'] = pd.to_datetime(df['Date'])
        df['Date'] = df['Date'].dt.date
        df = df[df['Date']==self._valueDate]
        if df.empty:
            raise Exception(f"No data found for {self._valueDate}")
        df = df.reset_index(drop=True)
        for col in df.columns:
            if col == 'Date':
                continue
            if 'Mo' in col:
                _date = self._valueDate + relativedelta(months=int(col.split(' ')[0]))
            elif 'Yr' in col:
                _date = self._valueDate + relativedelta(years=int(col.split(' ')[0]))
            elif 'SVEN' in col:
                _date = self._valueDate + relativedelta(years=int(col[-2:]))
            _rate = float(df.loc[0, col]) / 100
            self.append_data(_rate, _date)
        self._numRate = len(self._data)
