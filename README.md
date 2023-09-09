**Files and folders:**
- data
  - bonds.csv:\
    list of IBM bonds;
  - treasuryparcurve.csv\
    Treasury par yield curve, source [1].
  - treasuryspotcurve.csv\
    Treasury spot yield curve, source [2].
- service
  - app.py\
    The startup script for the Flask service.
- bond.py\
  The class for a bond structure.
- coupon.py\
  The class for a coupon date and rate.
- curve.py\
  The class for a curve.
- oas.py\
  The trinomial tree model implementation to calculate implied spread
- requirement.txt\
  Python packages required for this project.
- run.py\
  Start up script to pricing bonds
- utilities.py\
  Utility functions including yearfrac calculation, bisection method, etc.
- yieldcalculator.py\
  Collection of functions to calculate yields.
- notebook.ipynb
  The Jupyter notebook for demo.

**Environment**

Python Version >= 3.8 running on Ubuntu 20.04.\
Create and activate the virtual environment:
```
$ python3 -m venv env
$ source env/bin/activte
```

**Run Jupyter notebook demo**\
```
$ jupyter notebook
```
Open the notebook.ipynb file in web browser.

**Run Flask server**
```
$ cd service
$ export FLASK_APP=app.py
$ flask run
```

**About the curve**

To calculate the yield spread over treasury, use Treasuy Par Yield Curve, reference [2].

To calculate the implied option-adjusted spread, use Treasury zero coupon yield curve, reference [1].


**About the yield and spread**

YTM and YTC (if callable) are calculated using bisection method. Assuming the call period is from the next call date to maturity, call at par.
YTW (yield to worst) is YTM if non-callable. For a callable bond, the calculate the yield starting from next date to maturity, step is 7 days, get the worst yield.
Spread is to comparte with the treasury par yield. If interpolation is required, Linear interpolation will be used. If not required, find the cloest point in the yield curve.


**About JTD**

Assume the bond is default today, recovery rate 75%, LGD is given by,
LGD = max((Market Price - Recovery Rate), 0)

I'm not sure quite sure about the shocks or scenarios mentioned in question C 2. So it is not calculated here. In practice, we have define scenarios and calculate the theorectical prices for stress testing purpose. Below are some examples:

1. Interest Rate Up 5%.
2. Interest Rate up 25%.
3. Interest Rate Down 5%.
4. Interest Rate Down 25%.
5. Credit spread tighten 5%.
6. Credit spread widden 5%.

To parallelly shift the curve by an amount, call _add_shift_to_rate_tree() function, then call _calculate_values() to get the thx price.

**About pricing model**

I'm not able to design a model so I implemente the trinomial model, reference [3], which is a popular model for pricing options. Step is first to build the interest rate tree matrix and the probility at each node. Then starting from the leaf branch, discount the price back to the upper level, if the bond is callable, the price at the node is the lower of the price and call price. Given the time limitation, this has not been fully tested.

**Assumptions, issues:**
1. Missing Day Count info, this is needed to calculate year frac. Assuming Act/360 in this solution.
2. Missing first coupon date or accrual start date, this is needed to calculate coupon schedule. Using maturity date to backward coupon dates until reaching the earliest date which is later than issue date in this solution.
3. IR Vol assume 20%, mean version 5%. In practice, these need to be calibrated to market data.
4. This is a very simplied model implementation, and only works for callable and non-callable bonds and the call schedule is assumed to be one call only. In reality, call schedule can be mutliple steps with difference call prices. 
5. Putable bond are not supported. Floating rate bonds are not supported.



References

[1] US Treasury Zero-Coupon Yield Curve: https://data.nasdaq.com/data/FED/SVENY-us-treasury-zerocoupon-yield-curve

[2] US Treasury Par Yield Curve: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2023/all?field_tdr_date_value=2023&type=daily_treasury_yield_curve&page&_format=csv

[3] Implement the Hull-White trinomial tree model: https://media.thinkbrg.com/wp-content/uploads/2020/06/19094710/673_673_McCrary_HullWhite_Whitepaper_20160908.pdf