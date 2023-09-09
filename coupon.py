from datetime import date


class Coupon():
    def __init__(self, cpn_date: date, cpn_rate: float) -> None:
        self.couponDate = cpn_date
        self.couponRate = cpn_rate
        self.couponTenor = None

    def __str__(self) -> None:
        return f"{self.couponDate.strftime('%Y-%m-%d')}\t{self.couponRate}"


