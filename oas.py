from __future__ import annotations
import math
import copy
from bond import Bond
from curve import Curve
from datetime import date, datetime
import utilities

class OASModel():
    def __init__(self) -> None:
        self._valueDate = None
        self._bond = None
        self._curve = None
        self._yearly_time_step = 100
        self._dT = 0
        self._numT = 0
        self._vol = 0
        self._a = 0  # ir mean reversion
        self._j_max = 0
        self._num_yrs = 0

        self._u = 0
        self._d = 0
        self._credit_spread = 0
        self._p = nodeProbability()
        self._rateTree = None

        self._numCoupon = 0 # num of future coupons
        self._couponDates = None
        self._couponRates = None
        self._couponTenors = None
        self._couponAmounts = None
        self._accruedInterest = .0
        self._cpnSchedule = None
        self._callPrice = None

        self.priceNode = 0 # current value, dirty price
        self.priceNode1 = 0 # next step value
        self.priceUp = []
        self.priceDown = []
        self.priceUp1 = []
        self.priceDown = []


    def _set_tree_params(self):
        self._dT = 1.0 / self._yearly_time_step
        self._num_yrs = (utilities.toDateNumber(self._bond.Maturity) - utilities.toDateNumber(self._valueDate)) / 365.25
        self._numT = int(self._num_yrs / self._dT + 0.1)
        self._vol = self._curve._ir_vol
        self._a = self._curve._mean_reversion
        self._j_max = int(0.184 * self._yearly_time_step / self._a ) # / 4)
        self._u = math.exp(self._vol * math.sqrt(3.0 * self._dT))
        self._d = 1.0 / self._u
        self._p.setJmax(self._j_max)
        self._p.setNodeProbability(self._dT, self._a)

    def _set_rate_tree(self):
        if self._numT < 0:
            return
        self._rateTree = []

        #First Stage
        for i in range(self._numT+ 1):
            length = min(i, self._j_max)
            tree = treeBranch()
            tree.setBranch(length)
            tree.setUpBranch(self._u, self._j_max)
            tree.setDownBranch(self._d, self._j_max)
            self._rateTree.append(tree)

        # second stage
        err = self._rateTree[0].adjustTreeNodes(self._curve, self._dT, 0, self._p)
        if err == -1:
            return

        for i in range(1, self._numT+1):
            date_num = utilities.toDateNumber(self._curve._valueDate) + (i+1) * self._dT* 365.25
            rate = self._curve.getTheRate(date_num) 
            rate = utilities.DCToCC(rate, 2)
            dF = math.exp(-1 * rate * (i+1) * self._dT)
            err = self._rateTree[i].adjustTreeNodes(self._curve, self._dT, self._rateTree[i-1], self._p)
            if err == -1:
                return

            multiplier = self._rateTree[i].calcRatesAdjustMultiplier(self._dT, dF)
            if multiplier < 0:
                print("cannot find multiplier")
                return
            self._rateTree[i].adjustRatesByMultiplier(multiplier)

    def _set_credit_spread(self, credit_spread):
        self._credit_spread = credit_spread

    def _set_credit_spread_to_rate_tree(self):
        for i in range(self._numT+1):
            self._rateTree[i].adjustRatesByCreditSpread(self._credit_spread)

    def _set_future_coupons(self):
        nextCpnIdx = max(self._bond._get_next_date_idx(self._valueDate), 1)
        self._numCoupon = self._bond._numCoupon - nextCpnIdx + 1
        if self._numCoupon <= 0:
            return

        offset = self._bond._numCoupon - self._numCoupon
        self._couponDates = []
        self._couponRates = []
        self._couponTenors = []
        self._couponAmounts = []

        for i in range(self._numCoupon):
            self._couponDates.append(self._bond._coupon_schedule[offset+1+i].couponDate)
            self._couponRates.append(self._bond._coupon_schedule[offset+i].couponRate)
            self._couponTenors.append(self._bond._coupon_schedule[offset+i].couponTenor)
            self._couponAmounts.append(self._bond.FaceValue * self._couponRates[i] * self._couponTenors[i])
        
    def _set_accrued_interest(self):
        idx = self._bond._get_next_date_idx(self._valueDate)
        if idx == 0 or idx > self._bond._numCoupon:
            self._accruedInterest = 0.0
            return

        self._accruedInterest = self._bond.FaceValue * self._bond._coupon_schedule[idx-1].couponRate * utilities.calcYearFrac(self._bond._coupon_schedule[idx-1].couponDate, self._valueDate, self._bond.DayCount)

    def _set_cpn_schedule(self):
        self._cpnSchedule = [0.0] * (self._numT + 1)
        begin, end = -2, -2
        for i in range(self._numCoupon):
            if self._couponDates[i] < self._valueDate:
                continue
            begin = int((utilities.toDateNumber(self._couponDates[i]) - utilities.toDateNumber(self._valueDate)) / 365.25 / self._dT + 0.000001)
            if begin == end:
                begin += 1
            end = int( (utilities.toDateNumber(self._couponDates[i]) - utilities.toDateNumber(self._valueDate)) / 365.25 / self._dT + 0.000001)
            begin = max(begin, 0)
            end = max(begin, end)
            end = min(end, self._numCoupon - 1)
            j = begin
            while j <= end:
                self._cpnSchedule[j] = self._couponAmounts[i]
                j += 1

            if end == self._numT:
                break

    def _set_ai_schedule(self):
        self._AISchedule = [0.0] * (self._numT + 1)
        nextDateIdx = self._bond._get_next_date_idx(self._valueDate)

        for i in range(self._numT):
            t = i * self._dT * 365.25 + utilities.toDateNumber(self._valueDate)

            while nextDateIdx <= self._bond._numCoupon and t > utilities.toDateNumber(self._bond._coupon_schedule[nextDateIdx].couponDate):
                nextDateIdx += 1

            if nextDateIdx == 0 or nextDateIdx > self._bond._numCoupon:
                self._AISchedule[i] = 0.0
            else:
                self._AISchedule[i] = self._bond.FaceValue * self._bond._coupon_schedule[nextDateIdx-1].couponRate * utilities.calcYearFrac(utilities.toDateNumber(self._bond._coupon_schedule[nextDateIdx-1].couponDate), t, self._bond.DayCount)
    
    def _set_call_schedule(self):
        self._callPrice = [1.0e+50] * (self._numT + 1)
        if not self._bond.NextCallDate:
            return
        for i in range(self._numT):
            t = i * self._dT * 365.25 + utilities.toDateNumber(self._valueDate)
            if t >= utilities.toDateNumber(self._bond.NextCallDate):
                self._callPrice[i] = self._bond.NextCallPrice

    def _add_shift_to_rate_tree(self, shift: float):
        for i in range(self._numT+1):
            self._rateTree[i].adjustRatesByCreditSpread(shift)

    def _calculate_values(self):
        price_length = min(self._numT + 1, self._j_max)
        if price_length <= 0:
            return -1

        # normal case probability
        probUp = self._p.getProbUp()
        probMid = self._p.getProbMid()
        probDown = self._p.getProbDown()

        self.priceNode = .0
        self.priceUp = [.0] * price_length
        self.priceDown = [.0] * price_length

        self.priceNode1 = .0
        self.priceUp1 = [.0] * price_length
        self.priceDown1 = [.0] * price_length


        # terminal value
        self.priceNode1 = self._bond.Redemption + self._cpnSchedule[self._numT]
        callPay = self._callPrice[self._numT] + self._AISchedule[self._numT]
        if self.priceNode1 >= self._callPrice[self._numT]:
            self.priceNode1 = min(self.priceNode1, callPay)
        for i in range(price_length):
            self.priceUp1[i] = self._bond.Redemption + self._cpnSchedule[self._numT]
            if self.priceUp1[i] >= self._callPrice[self._numT]:
                self.priceUp1[i] = min(self.priceUp1[i], callPay)
            self.priceDown1[i] = self._bond.Redemption + self._cpnSchedule[self._numT]
            if self.priceDown1[i] >= self._callPrice[self._numT]:
                self.priceDown1[i] = min(self.priceDown1[i], callPay)

        # go backwards from _numT - 1 to 0
        for i in reversed(range(self._numT)):
            size = self._rateTree[i].getSize()
            rate = .0
            p1, p2, p3 = .0, .0, .0  # probabilities
            v1, v2, v3 = .0, .0, .0  # values

            callPay = self._callPrice[i] + self._AISchedule[i]
            callTriggerPrice = self._callPrice[i]

            # upper half
            for j in range(size):
                rate = self._rateTree[i].getUpRate(j)
                if j < self._j_max - 1:
                    index = self._p.findIndex(j+1)
                    if index == -1:
                        return -1

                    p1 = probUp[index]
                    p2 = probMid[index]
                    p3 = probDown[index]
                    
                    v1 = self.priceUp1[j+1]
                    v2 = self.priceUp1[j]
                    v3 = self.priceUp1[j-1] if j > 0 else self.priceNode1

                else:  # j=j_max-1
                    p1 = self._p.getTopProbHigh()
                    p2 = self._p.getTopProbMid()
                    p3 = self._p.getTopProbLow()

                    v1 = self.priceUp1[j]
                    v2 = self.priceUp1[j-1]
                    v3 = self.priceUp1[j-2]

                self.priceUp[j] = (p1 * v1 + p2 * v2 + p3 * v3) * math.exp(-1 * rate * self._dT) + self._cpnSchedule[i]

                if self.priceUp[j] >= callTriggerPrice:
                    self.priceUp[j] = min(self.priceUp[j], callPay)

            # center node	
            rate = self._rateTree[i].getNodeRate()
            index = self._p.findIndex(0)
            p1 = probUp[index]
            p2 = probMid[index]
            p3 = probDown[index]

            v1 = self.priceUp1[0]
            v2 = self.priceNode1
            v3 = self.priceDown1[0]

            self.priceNode = (p1 * v1 + p2 * v2 + p3 * v3) * math.exp(-1 * rate * self._dT) + self._cpnSchedule[i]
                        
            if self.priceNode >= callTriggerPrice:
                self.priceNode = min(self.priceNode, callPay)

            # lower half
            for j in range(size):
                rate = self._rateTree[i].getDownRate(j)
            
                if j < self._j_max-1:
                    index = self._p.findIndex(-j-1)
                
                    if index == -1:
                        return -1

                    p1 = probUp[index]
                    p2 = probMid[index]
                    p3 = probDown[index]
                    
                    v1 = self.priceDown1[j-1] if j > 0 else self.priceNode1
                    v2 = self.priceDown1[j]
                    v3 = self.priceDown1[j+1]
                else:  # j == j_max-1
                    p1 = self._p.getBottomProbHigh()
                    p2 = self._p.getBottomProbMid()
                    p3 = self._p.getBottomProbLow()

                    v1 = self.priceDown1[j-2]
                    v2 = self.priceDown1[j-1]
                    v3 = self.priceDown1[j]
                
                self.priceDown[j] = (p1 * v1 + p2 * v2 + p3 * v3) * math.exp(-1 * rate * self._dT) + self._cpnSchedule[i]
                if self.priceDown[j] >= callTriggerPrice:
                    self.priceDown[j] = min(self.priceDown[j], callPay)

            if i > 0:
                self.priceDown1 = copy.deepcopy(self.priceDown)
                self.priceUp1 = self.priceUp
                self.priceNode1 = self.priceNode
        return 0

    def get_dirty_price(self):
        return self.priceNode

    def get_price(self):
        return self.priceNode - self._accruedInterest

    def Calculate_OAS(self, bond: Bond, curve: Curve, value_date: date, price: float, credit_spread: float):
        ''' Return:
              the implied credit spread for the market price
            Params:
              bond: the Bond
              curve: the Curve
              value_date: pricing date (settlement date)
              price: market price
              credit_spread: seed
        '''
        self._bond = bond
        self._curve = curve
        self._valueDate = value_date

        self._set_tree_params()
        self._set_credit_spread(credit_spread)
        self._set_rate_tree()
        self._set_credit_spread_to_rate_tree()
        self._set_future_coupons()
        self._set_accrued_interest()
        self._set_cpn_schedule()
        self._set_ai_schedule()
        self._set_call_schedule()
        self._calculate_values()

        dirty_price = self.get_dirty_price()
        clean_price = self.get_price()

        diff = clean_price - price

        count = 0 # num of iterations
        while math.fabs(diff) > 0.01 and count < 10:
            self._add_shift_to_rate_tree(10 * 0.0001) # change by 1 bp
            err = self._calculate_values()
            if err == -1:
                return -1

            dirty_price2 = self.get_dirty_price()
            spread_rho = (dirty_price2 - dirty_price) / 0.001

            if math.fabs(spread_rho) < 0.001:
                return credit_spread

            credit_spread -= diff / spread_rho
            self._set_credit_spread(credit_spread);  # set new credit spread
            self._add_shift_to_rate_tree(-10 * 0.0001 - diff / spread_rho)

            err = self._calculate_values()
            if err == -1:
                return -1

            dirty_price = self.get_dirty_price()
            clean_price = self.get_price()
            diff = clean_price-price

            count += 1

        return credit_spread


class nodeProbability():
    def __init__(self) -> None:
        self.j_max = 0
        self.prob_up = []   #for j=-j_max+1, -j_max+2,  -1, 0, 1, 2, ..., j_max-1;	
        self.prob_mid = []  #array size = 1 + 2*(j_max-1);
        self.prob_down = [] #i <----> i - j_max + 1.   

        # at j_max
        self.ptop_h = 0 
        self.ptop_m = 0 
        self.ptop_l = 0 

        # at -j_max
        self.pbot_h = 0
        self.pbot_m = 0
        self.pbot_l = 0
        
    def getJmax(self):
        return self.j_max

    def getProbUp(self):
        return self.prob_up

    def getProbMid(self):
        return self.prob_mid

    def getProbDown(self):
        return self.prob_down
    
    def getTopProbHigh(self):
        return self.ptop_h
    def getTopProbMid(self):
        return self.ptop_m
    def getTopProbLow(self):
        return self.ptop_l

    def getBottomProbHigh(self):
        return self.pbot_h

    def getBottomProbMid(self):
        return self.pbot_m

    def getBottomProbLow(self):
        return self.pbot_l

    def setJmax(self, j: int):
        self.j_max =j

    def findIndex(self, j: int) -> int:
        ''' j=-j_max+1, -j_max+2, ..., -1, 0, 1, 2,.., j_max-1
        '''
        if j <= -1 * self.j_max or  j >= self.j_max:
            print("index out of bound for probability")
            return -1
        return j + self.j_max-1

    def setNodeProbability(self, dT: float, a: float):
        if self.prob_up:
            self.prob_up = []

        if self.prob_mid:
            self.prob_mid = []

        if self.prob_down:
            self.prob_down = []

        for i in range(2 * self.j_max - 1):
            j = i - self.j_max + 1
            self.prob_up.append(1.0 /6.0 + (a*a*j*j*dT*dT - a*j*dT)/2.0)
            self.prob_mid.append(2.0/3.0 - a*a*j*j*dT*dT)
            self.prob_down.append(1 - self.prob_up[i] - self.prob_mid[i])

        # at j_max
        self.ptop_h = (7.0/6.0) + (a*a*self.j_max*self.j_max*dT*dT - 3*a*self.j_max*dT)/2.0  #no rate change
        self.ptop_m = -(1.0/3.0) - a*a*self.j_max*self.j_max*dT*dT + 2*a*self.j_max*dT  # 1 down
        self.ptop_l = 1 - self.ptop_h - self.ptop_m   # 2*down

        # at -j_max
        self.pbot_h = (1.0/6.0) + (a*a*self.j_max*self.j_max*dT*dT + a*(-1 * self.j_max)*dT)/2.0  # 2*up
        self.pbot_m = -1.0/3.0 - a*a*self.j_max*self.j_max*dT*dT - 2*a*(-1 * self.j_max)*dT  # 1 up
        self.pbot_l = 1 - self.pbot_h - self.pbot_m   # no rate change


class treeBranch():
    def __init__(self, size: int=0) -> None:
        # total nodes 2*size+1
        # the rates nodes
        self.node = 1.0
        self.up = [1.0] * size if size > 0 else []  # float
        self.down = [1.0] * size if size > 0 else []
        self.size = size

        # the Q nodes, i.e. the present value of $1 at this node, $0 at other nodes.
        self.qNode = .0
        self.qUp = [.0] * size if size > 0 else []  # float
        self.qDown = [.0] * size if size > 0 else [] # float

    def setBranch(self, n: int):
        self.size = n
        self.node = 1.0
        self.up = [1.0] * self.size if self.size > 0 else []  # float
        self.down = [1.0] * self.size if self.size > 0 else []

        # the Q nodes, i.e. the present value of $1 at this node, $0 at other nodes.
        self.qNode = .0
        self.qUp = [.0] * self.size if self.size > 0 else []  # float
        self.qDown = [.0] * self.size if self.size > 0 else [] # float

    def setUpBranch(self, u: float, limit: int):  # limit is the index where the branch reverts.
        if self.size <= 0:
            return

        self.up[0] = u

        for i in range(1, self.size):
            if i < limit:
                self.up[i] = self.up[i-1] * u
            else:
                self.up[i] = self.up[i-1]
            
    def setDownBranch(self, d: float, limit: int):
        if self.size <= 0:
            return

        self.down[0] = d

        for i in range(1, self.size):
            if i < limit:
                self.down[i] = self.down[i-1] * d
            else:
                self.down[i] = self.down[i-1]

    def getQNode(self):
        return self.qNode
    
    def getQUpNode(self):
        return self.qUp
    
    def getQDownNode(self):
        return self.qDown
    
    def getSize(self):
        return self.size
    
    def getUpNode(self):
        return self.up
    
    def getDownNode(self):
        return self.down
    def getNode(self):
        return self.node

    def adjustTreeNodes(self, curve: Curve, dT: float, prev: treeBranch, p: nodeProbability) -> int:
        today = curve._valueDateNum
        j_max = p.getJmax()
        index = 0
        temp = .0

        if self.size == 0:
            self.node = curve.getTheRate(today + 365.25 * dT) # semi-annual compounded rate
            self.node = utilities.DCToCC(self.node, 2)
            self.qNode = 1
            return 0

        preQUp = prev.getQUpNode()
        preQDown = prev.getQDownNode()
        preQNode = prev.getQNode()

        preRUp = prev.getUpNode()
        preRDown = prev.getDownNode()
        preRNode = prev.getNode()

        # normal case probability
        probUp = p.getProbUp()
        probMid = p.getProbMid()
        probDown = p.getProbDown()

        # set qNode first; assume j_max>2
        q1, q2, q3 = 0.0, .0, .0
        r1, r2, r3 = .0, .0, .0 # rates in prev branch
        p1, p2, p3 = .0, .0, .0 #probability from the prev node to qNode.
        pre_size = prev.getSize()

        if self.size>1:
            q1 = preQUp[0]
            r1 = preRUp[0]
            
            index = p.findIndex(1)
            if index == -1:
                return -1

            p1 = probDown[index]

            q3 = preQDown[0]
            r3 = preRDown[0]
            index = p.findIndex(-1)

            if index == -1:
                return -1

            p3 = probUp[index]
        else:
            q1, r1, p1 = .0, .0, .0
            q3, r3, p3 = .0, .0, .0

        q2 = preQNode
        r2 = preRNode

        index = p.findIndex(0)
        if index==-1:
            return -1
        p2 = probMid[index]

        self.qNode = q1 * p1 * math.exp(-r1*dT) + q2 * p2 * math.exp(-r2*dT) + q3 * p3 * math.exp(-r3*dT)
        
        #upper half.
        for i in range(self.size):
            self.qUp[i] = 0

            if i > pre_size-1:
                q1, r1, p1 = .0, .0, .0
                q2, r2, p2 = .0, .0, .0
                if i>0:
                    q3 = preQUp[i-1]
                    r3 = preRUp[i-1]

                    index = p.findIndex(i)
                    if index == -1:
                        return -1
                    p3 = probUp[index]
                else:
                    q3 = preQNode
                    r3 = preRNode
                    
                    index = p.findIndex(0)
                    if index==-1:
                        return -1
                    p3 = probUp[index]
            elif i == pre_size - 1:
                q1, r1, p1 = .0, .0, .0
                # q2 might be at j_max level in this case
                q2 = preQUp[i]
                r2 = preRUp[i]
                
                if i == j_max-1:
                    p2 = p.getTopProbHigh()
                else:
                    index = p.findIndex(i+1)
                    if index==-1:
                        return -1
                    p2 = probMid[index]

                if i==0:
                    q3 = preQNode
                    r3 = preRNode
                    
                    index = p.findIndex(0)
                    if index==-1:
                        return -1
                    p3 = probUp[index]
                else:
                    q3 = preQUp[i-1]
                    r3 = preRUp[i-1]
                    index = p.findIndex(i)
                    if index == -1:
                        return -1
                    p3 = probUp[index]
            else:  #i < pre_size-1 case
                q1 = preQUp[i+1]
                r1 = preRUp[i+1]
                if i+2 == j_max:
                    p1 = p.getTopProbMid()
                else:
                    index = p.findIndex(i+2)
                    if index == -1:
                        return -1
                    p1 = probDown[index]

                q2 = preQUp[i]
                r2 = preRUp[i]
                index = p.findIndex(i+1)

                if index==-1:
                    return -1
                p2 = probMid[index]

                if i > 0:
                    q3 = preQUp[i-1]
                    r3 = preRUp[i-1]
                    index = p.findIndex(i)
                    if index == -1:
                        return -1
                    p3 = probUp[index]
                else: # i==0 case
                    q3 = preQNode
                    r3 = preRNode
                    index = p.findIndex(0)
                    
                    if index == -1:
                        return -1
                    p3=probUp[index]

                #this case may never happen in practice
                if i+3 == j_max and (i+2)<pre_size:
                    q0 = preQUp[i+2]
                    r0 = preRUp[i+2]
                    p0 = p.getTopProbLow()

                    temp = q0 * p0 * math.exp(-r0*dT)
                    self.qUp[i] += temp

            temp = (q1 * p1 * math.exp(-r1*dT) + q2 * p2 * math.exp(-r2*dT) + q3*p3*math.exp(-r3*dT))
            self.qUp[i] += temp

        # lower half
        for i in range(self.size):
            self.qDown[i] = 0

            if i > pre_size-1:
                q3, r3, p3 = .0, .0, .0
                q2, r2, p2 = .0, .0, .0
                if i > 0:
                    q1 = preQDown[i-1]
                    r1 = preRDown[i-1]
                    index = p.findIndex(-i)
                    
                    if index == -1:
                        return -1
                    p1 = probDown[index]
                else:
                    q1 = preQNode
                    r1 = preRNode
                    index = p.findIndex(0)
                    
                    if index == -1:
                        return -1
                    p1 = probDown[index]
            elif i == pre_size - 1:
                q3, r3, p3 = .0, .0, .0
                
                # q2 might be at -j_max level in this case
                q2 = preQDown[i]
                r2 = preRDown[i]

                if i == j_max-1:
                    p2 = p.getBottomProbLow()
                else:
                    index = p.findIndex(-i-1)
                    if index == -1:
                        return -1
                    p2 = probMid[index]

                if i == 0:
                    q1 = preQNode
                    r1 = preRNode
                    index = p.findIndex(0)
                    if index == -1:
                        return -1
                    p1 = probDown[index]
                else:
                    q1 = preQDown[i-1]
                    r1 = preRDown[i-1]
                    index = p.findIndex(-i)
                    if index == -1:
                        return -1
                    p1 = probDown[index]
            else:   #i<presize-1 case
                q3 = preQDown[i+1]
                r3 = preRDown[i+1]
                
                if i+2 == j_max:
                    p3 = p.getBottomProbMid()
                else:
                    index = p.findIndex(-i-2)
                    if index == -1:
                        return -1
                    p3 = probUp[index]

                q2 = preQDown[i]
                r2 = preRDown[i]
                index = p.findIndex(-i-1)
                if index == -1:
                    return -1

                p2 = probMid[index]

                if i > 0:
                    q1 = preQDown[i-1]
                    r1 = preRDown[i-1]
                    index = p.findIndex(-i)

                    if index == -1:
                        return -1
                    p1 = probDown[index]
                else:
                    q1 = preQNode
                    r1 = preRNode
                    index = p.findIndex(0)
                    if index == -1:
                        return -1
                    p1=probDown[index]

                if i+3 == j_max and (i+2)<pre_size:
                    q0 = preQDown[i+2]
                    r0 = preRDown[i+2]
                    p0 = p.getBottomProbHigh()

                    temp = q0 * p0 * math.exp(-r0*dT)
                    self.qDown[i] += temp

            temp = q1 * p1 * math.exp(-r1*dT) + q2 * p2 * math.exp(-r2*dT) + q3 * p3 * math.exp(-r3*dT)
            self.qDown[i] += temp
        return 0
    
    def calcRatesAdjustMultiplier(self, dT: float, dF: float)-> float:
        left, mid, right = 0, 0, 1
        sum_l, sum_r, sum = 0, 0, 0
        sum_l += self.qNode * math.exp(-left * self.node * dT)
        sum_r += self.qNode * math.exp(-right * self.node * dT)

        for i in range(self.size):
            temp = self.qUp[i] * math.exp(-1 * left * self.up[i] * dT)
            sum_l += temp

            temp = self.qDown[i] * math.exp(-1 * left * self.down[i] * dT)
            sum_l += temp

            temp = self.qUp[i] * math.exp(-1 * right * self.up[i] * dT)
            sum_r += temp

            temp = self.qDown[i] * math.exp(-1 * right * self.down[i] * dT)
            sum_r += temp

        # error
        if sum_l < dF or sum_r > dF:
            return -1

        sum = sum_r
        mid = right

        while math.fabs(sum - dF) > 0.000001 and math.fabs(left-right) > 0.00001:
            mid = (left + right) / 2
            sum = self.qNode * math.exp(-1 * mid * self.node * dT)
            
            for i in range(self.size):
                temp = self.qUp[i] * math.exp(-1 * mid * self.up[i] * dT)
                if temp < 1.0e-50 or temp > 1.0e+50:
                    temp=0
                sum += temp
                
                temp = self.qDown[i] * math.exp(-1 * mid * self.down[i]*dT)
                if temp < 1.0e-50 or temp > 1.0e+50:
                    temp=0
                sum += temp

            if sum < dF:
                right = mid

            if sum > dF:
                left=mid

        return mid

    def adjustRatesByMultiplier(self, multiplier: float) -> None:
        self.node = multiplier * self.node
        for i in range(self.size):
            self.up[i] = multiplier * self.up[i]
            self.down[i] = multiplier * self.down[i]

    def adjustRatesByCreditSpread(self, credit_spread: float):
        self.node = utilities.CCToDC(self.node, 2) 
        self.node += credit_spread
        self.node = utilities.DCToCC(self.node, 2)  

        for i in range(self.size):           
            self.up[i] = utilities.CCToDC(self.up[i], 2)
            self.up[i] += credit_spread
            self.up[i] = utilities.DCToCC(self.up[i], 2)

            self.down[i] = utilities.CCToDC(self.down[i], 2)
            self.down[i] += credit_spread
            self.down[i] = utilities.DCToCC(self.down[i], 2)

    def adjustRatesByRemoveCreditSpread(self, credit_spread: float):
        self.node = utilities.CCToDC(self.node, 2)
        self.node -= credit_spread
        self.node = utilities.DCToCC(self.node, 2)

        for i in range(self.size):
            self.up[i] = utilities.CCToDC(self.up[i], 2)
            self.up[i] -= credit_spread
            self.up[i] = utilities.DCToCC(self.up[i], 2)

            self.down[i] = utilities.CCToDC(self.down[i], 2)
            self.down[i] -= credit_spread
            self.down[i] = utilities.DCToCC(self.down[i], 2)

    def getNodeRate(self):
        return self.node

    def getUpRate(self, index: int):
        return self.up[index]

    def getDownRate(self, index: int):
        return self.down[index]
