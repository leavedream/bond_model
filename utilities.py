import math
from datetime import date
def calcYearFrac(date_from: [date, float], date_to: [date, float], day_count='ACT/360'):
    if isinstance(date_from, float):
        return (date_to - date_from) / 360.0
    return (date_to - date_from).days / 360.0


def bisectSolve(func, **param) -> float:
    leftBracket, rightBracket, solutionAccuracy, functionAccuracy = -0.9999, 1000.0, 1E-6, 1E-6
    mid, leftF, rightF, midF = .0, .0, .0, .0

    leftF  = func(leftBracket,  **param)
    rightF = func(rightBracket, **param)

    if abs(leftF) < functionAccuracy: 
        return leftBracket

    if abs(rightF) < functionAccuracy:
        return rightBracket

    if leftF * rightF > 0.0 :
        raise ValueError(f"Same sign in bisectSolve()")

    while rightBracket - leftBracket > solutionAccuracy:
        mid  = 0.5 * ( leftBracket + rightBracket )
        midF = func(mid, **param)

        if abs(midF) < functionAccuracy:
            return mid

        if midF * leftF < 0.0 :
            rightBracket = mid
        else:
            leftBracket  = mid


    return 0.5 * ( leftBracket + rightBracket)

def toDateNumber(the_date: date) -> float:
    delta = the_date - date(1899, 12, 31)
    return float(delta.days) + float(delta.seconds) / 86400


# Conversion between discrete and continuous compounded rates */
def DCToCC(dRate: float, freq: int) -> float:
    return freq * math.log(1.0 + dRate / freq)

def CCToDC(cRate: float, freq: int) -> float:
    return freq * (math.exp(cRate / freq) - 1.0)

def linear_interpolation(date1: [date, float], yield1: float, date2: [date, float], yield2: float, val_date: [date, float]):
    if isinstance(date1, date):
        date1 = toDateNumber(date1)
    if isinstance(date2, date):
        date2 = toDateNumber(date2)
    if isinstance(val_date, date):
        val_date = toDateNumber(val_date)
    
    return yield2 + (val_date - date2) * (yield1 - yield2) / (date1 - date2)
