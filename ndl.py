"""
https://joorev.com/nitrox/

Following Erik C. Baker's paper on calculating NDLs, we have the following:

Definitions:
P = Final partial pressure in a given compartment
Pamb = Ambient pressure at depth
PH2O = water vapor pressure
FN2 = Nitrogen partial pressure at surface
Pi = Inspired pressure, e.g. ambient pressure minus water vapor pressure
Po = Initial compartment pressure
k = time constant for the current tissue compartment
t = NDL for the current tissue compartment

We start with the basic Haldane equation:
P = Po + (Pi - Po)(1 - e^-kt)

We rearrange the Haldane equation to solve for time, t:
(P - Po)/(Pi - Po) = 1 - e^-kt
e^-kt = 1 - (P - Po)/(Pi - Po)

We simplify the equation:
e^-kt = (Pi - Po)/(Pi - Po) - (P - Po)/(Pi - Po)
e^-kt = (Pi - Po - P + Po)/(Pi - Po)
e^-kt = (Pi - P)/(Pi - Po)

We take the natural logarithm of both sides, to extract t (time):
ln[e^-kt] = ln[(Pi - P)/(Pi - Po)]
-kt = ln[(Pi - P)/(Pi - Po)]
t = (-1/k)*ln[(Pi - P)/(Pi - Po)]

Lastly, we substitute the surfacing M-value, Mo, for the final pressure, P:
t = (-1/k)*ln[(Pi - Mo)/(Pi - Po)]

"""