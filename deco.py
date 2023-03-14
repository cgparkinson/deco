from abc import ABC
from typing import List, Sequence
import numpy as np

SURFACE_OXYGEN = 0.21
SURFACE_NITROGEN = 0.79
assert SURFACE_OXYGEN + SURFACE_NITROGEN == 1

WV_PRESSURE = 0.0627

class Gas:
    def __init__(self, oxygen=21, helium=0, ppo2=1.4) -> None:
        self.oxygen = oxygen/100
        self.helium = helium/100
        self.nitrogen = 1 - self.oxygen - self.helium
        self.mod = self.get_mod(ppo2)
        self.min_od = self.get_min_od(ppo2)
        self.id = str(oxygen) + '/' + str(helium) + ' ' + str(ppo2)

    def get_mod(self, ppo2):
        return ppo2 / self.oxygen * 10 - 10
    
    def get_min_od(self, ppo2):
        return 0.16 / self.oxygen * 10 - 10

air = Gas()
air_tec = Gas(ppo2=1.2)
eanx32 = Gas(oxygen=32)
eanx32_tec = Gas(oxygen=32, ppo2=1.2)
deco_eanx50 = Gas(oxygen=50, ppo2=1.6)
deco_oxygen = Gas(oxygen=100, ppo2=1.6)
trimix_21_35 = Gas(oxygen=21, helium=35, ppo2=1.2)
trimix_18_45 = Gas(oxygen=18, helium=45, ppo2=1.2)
trimix_15_55 = Gas(oxygen=15, helium=55, ppo2=1.2)
trimix_12_65 = Gas(oxygen=12, helium=65, ppo2=1.2)

class DiveProfileCheckpoint:
    def __init__(self, time, depth, gas=air, state=None, validation=None) -> None:
        self.time = time
        self.depth = depth
        self.gas = gas
        self.state = state
        self.validation = validation

    def __repr__(self) -> str:
        return str((self.time, self.depth, self.state, self.validation))
    
    def __str__(self):
        return str((self.time, self.depth, self.state, self.validation))

class DiveProfile:
    def __init__(self, checkpoints: List[DiveProfileCheckpoint]) -> None:
        self.__checkpoints__ = checkpoints
        self.explode_checkpoints(checkpoints)

    def explode_checkpoints(self, checkpoints):
        assert checkpoints[0].time == 0
        assert checkpoints[0].depth == 0
        for i in range(len(checkpoints)-1):
            prev_ckpt = checkpoints[i]
            next_ckpt = checkpoints[i+1]
            assert prev_ckpt.time == int(prev_ckpt.time)
            assert next_ckpt.time == int(next_ckpt.time)
            assert prev_ckpt.time < next_ckpt.time
        self.profile = []
        for checkpoint in checkpoints:
            self.add_checkpoint(checkpoint)
    
    def delete_after(self, t):
        for i in reversed(range(len(self.profile))):
            if self.profile[i].time > t:
                self.profile.pop()
    
    def add_checkpoint(self, next_checkpoint):
        if self.profile:
            prev_checkpoint = self.profile[-1]
        else:
            self.profile.append(next_checkpoint)
            return None
        time_to_process = prev_checkpoint.time

        while time_to_process <= next_checkpoint.time:
            # get previous and next checkpoint
            if time_to_process == next_checkpoint.time:
                self.profile.append(next_checkpoint)
            else:
                prop_prev = (time_to_process - prev_checkpoint.time) / (next_checkpoint.time - prev_checkpoint.time)
                interpolated_depth = next_checkpoint.depth * prop_prev + prev_checkpoint.depth * (1-prop_prev)
                gas=prev_checkpoint.gas
                new_checkpoint = DiveProfileCheckpoint(time=time_to_process, depth=interpolated_depth, gas=gas)
                self.profile.append(new_checkpoint)
            time_to_process = time_to_process + 1
    
    def __getitem__(self, key):
        return self.profile[key]

    def __len__(self):
        return len(self.profile)

class DiveAlgorithm(ABC):
    def __calculate_states__(self, dive_profile: DiveProfile):
        # adds a state to each entry in the dive profile
        pass

    def __validate_states__(self, dive_profile: DiveProfile) -> bool:
        # decides if the state at each point in the dive profile is valid
        # returns a bool, True if all are valid
        pass

    def process(self, dive_profile: DiveProfile) -> bool:
        self.__calculate_states__(dive_profile)
        return self.__validate_states__(dive_profile)

class BuhlmannCompartment:
    def __init__(self, gf_hi, surfacing_m_value, m_value_slope, half_time_min) -> None:
        self.gf_hi = gf_hi  # TODO refactor again
        self.surfacing_m_value = surfacing_m_value  # in metres of sea water (10 msw = 1 bar = surface)
        self.m_value_slope = m_value_slope
        self.half_time_min = half_time_min
    
    def __repr__(self) -> str:
        return str(self.half_time_min)
    
    def __str__(self):
        return str(self.half_time_min)

class BuhlmannCompartmentState:
    def __init__(
        self,
        compartment: BuhlmannCompartment,
        current_checkpoint: DiveProfileCheckpoint=None,
        previous_checkpoint: DiveProfileCheckpoint=None
    ) -> None:
        self.compartment = compartment
        self.ndl=None
        if previous_checkpoint == None:
            self.ppn2 = (1 - WV_PRESSURE) * SURFACE_NITROGEN
            self.ceiling = self.calculate_ceiling(self.ppn2, compartment)
            self.ndl = 99
        else:
            prev_ppn2 = [
                bcs.ppn2 for bcs in previous_checkpoint.state if compartment == bcs.compartment  # note the object comparison
                ][0]
            inhaled_ppn2 = (1+(current_checkpoint.depth)/10 - WV_PRESSURE) * current_checkpoint.gas.nitrogen
            self.update_ppn2(
                compartment,
                inhaled_ppn2=inhaled_ppn2,
                time_spent=current_checkpoint.time - previous_checkpoint.time,
                prev_ppn2=prev_ppn2
            )
            self.ceiling = self.calculate_ceiling(self.ppn2, compartment)
            self.ndl = self.calculate_ndl(self.ppn2, compartment, inhaled_ppn2)
    
    def update_ppn2(self,
        compartment: BuhlmannCompartment,
        inhaled_ppn2,
        time_spent,
        prev_ppn2
        ):
        # this is the main algo
        self.ppn2 = prev_ppn2 + (inhaled_ppn2 - prev_ppn2) * (1 - 2 ** (-(time_spent / 60) / compartment.half_time_min))

    def calculate_ceiling(self, ppn2, compartment):
        surfacing_m_value=compartment.surfacing_m_value
        m_value_slope = compartment.m_value_slope
        gf=compartment.gf_hi  # TODO: is a gradient factor an attribute of a compartment?
        # TODO fix gradient factors
        surfacing_m_value_bar = surfacing_m_value/10 # body partial pressure limit for nitrogen
        gf_prop = gf/100
        adjusted_m_value_slope = m_value_slope*(gf_prop) + (1-gf_prop)  # weighted average of M-value slope and equilibrium
        adjusted_surfacing_m_value_bar = (surfacing_m_value_bar - 1) * gf_prop + 1
        """
        The Nitrogen constant NITROGEN should not appear here AT ALL. nobody cares what you're breathing. It's only the ppn2
        in your body compared to the pressure around you. That's all that's relevant for deco calculations.

        For offgassing, NITROGEN does come into play. Whether you're on- or off-gassing has nothing to do with the line y=x,
        it's related to what you're breathing.
        https://scubaboard.com/community/threads/ceiling-gf.568222/page-11#post-8433388

        Find M-value for a given ambient pressure.

        Ambient pressure = 1 means M-value = surfacing_m_value
        Ambient pressure = 2 means M-value = surfacing_m_value + m_value_slope_bar

        so M_value = surfacing_m_value + amb_press_bar * m_value_slope_bar

        now sub ppn2 = M_value and find amb_press_bar

        amb_press_bar = (ppn2 - surfacing_m_value) / m_value_slope_bar
        """
        # -1 is an offset to do with the intercept being zero absolute pressure not surface pressure?
        # TODO justify
        ceiling_bar = (ppn2 - adjusted_surfacing_m_value_bar) / adjusted_m_value_slope - 1
        ceiling = (ceiling_bar + 1) * 10
        if ceiling<0:
            return 0
        else:
            return ceiling
        
    def calculate_ndl(self, ppn2, compartment, inhaled_ppn2):
        import numpy as np
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
        k = time constant (base 2) for the current tissue compartment
        t = NDL for the current tissue compartment

        We start with the basic Haldane equation:
        P = Po + (Pi - Po)(1 - 2^-kt)

        We rearrange the Haldane equation to solve for time, t:
        (P - Po)/(Pi - Po) = 1 - 2^-kt
        2^-kt = 1 - (P - Po)/(Pi - Po)

        We simplify the equation:
        2^-kt = (Pi - Po)/(Pi - Po) - (P - Po)/(Pi - Po)
        2^-kt = (Pi - Po - P + Po)/(Pi - Po)
        2^-kt = (Pi - P)/(Pi - Po)

        We take the logarithm of both sides, to extract t (time):
        log[2^-kt] = log[(Pi - P)/(Pi - Po)]
        -kt*log(2) = log[(Pi - P)/(Pi - Po)]
        t = (-1/(k*log2))*log[(Pi - P)/(Pi - Po)]

        Lastly, we substitute the surfacing M-value, Mo, for the final pressure, P:
        t = (-1/(k*log2))*log[(Pi - Mo)/(Pi - Po)]
        """
        # TODO DRY
        surfacing_m_value=compartment.surfacing_m_value
        m_value_slope = compartment.m_value_slope
        gf=compartment.gf_hi  # TODO: is a gradient factor an attribute of a compartment?
        # TODO fix gradient factors
        surfacing_m_value_bar = surfacing_m_value/10 # body partial pressure limit for nitrogen
        gf_prop = gf/100
        adjusted_m_value_slope = m_value_slope*(gf_prop) + (1-gf_prop)  # weighted average of M-value slope and equilibrium
        adjusted_surfacing_m_value_bar = (surfacing_m_value_bar - 1) * gf_prop + 1
        if inhaled_ppn2 == ppn2:
            return 99
        ratio=(inhaled_ppn2 - adjusted_surfacing_m_value_bar)/(inhaled_ppn2 - ppn2)
        if ratio<=0:
            return 99
        if inhaled_ppn2 < ppn2:
            return 99
        ndl = (-compartment.half_time_min/(np.log(2)))*np.log(ratio)
        return 99 if np.isnan(ndl) else ndl

    def __repr__(self) -> str:
        return "halftime is " + str(self.compartment) + " ppN2 is " + str(self.ppn2)
    
    def __str__(self):
        return "halftime is " + str(self.compartment) + " ppN2 is " + str(self.ppn2)

class BuhlmannState(Sequence):
    # this will behave as a list of BuhlmannCompartmentState
    def __init__(self, compartments, prev_checkpoint: DiveProfileCheckpoint = None, cur_checkpoint: DiveProfileCheckpoint = None) -> None:
        if prev_checkpoint == None:
            state = [BuhlmannCompartmentState(compartment) for compartment in compartments]
        else:
            state = [BuhlmannCompartmentState(
                compartment,
                previous_checkpoint=prev_checkpoint,
                current_checkpoint=cur_checkpoint) for compartment in compartments]
        self.__state__ = state
    
    def __getitem__(self, key):
        return self.__state__[key]

    def __len__(self):
        return len(self.__state__)
    
    def __repr__(self) -> str:
        return str(self.__state__)
    
    def __str__(self):
        return str(self.__state__)

class Buhlmann_Z16C(DiveAlgorithm):
    def __init__(self, gf=100) -> None:
        # https://www.shearwater.com/wp-content/uploads/2019/05/understanding_m-values.pdf
        self.gf_hi=gf
        self.gf_lo=gf  # not used, much harder to implement
        self.compartments = [
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=29.65704, m_value_slope = 1.7928,half_time_min=5),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=25.35936, m_value_slope = 1.5352,half_time_min=8),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=22.49424, m_value_slope = 1.3847,half_time_min=12.5),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=20.36064, m_value_slope = 1.278,half_time_min=18.5),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=18.53184, m_value_slope = 1.2306,half_time_min=27),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=16.94688, m_value_slope = 1.1857,half_time_min=38.3),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=15.94104, m_value_slope = 1.1504,half_time_min=54.3),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=15.27048, m_value_slope = 1.1223,half_time_min=77),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=14.7828, m_value_slope = 1.0999,half_time_min=109),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=14.38656, m_value_slope = 1.0844,half_time_min=146),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=14.05128, m_value_slope = 1.0731,half_time_min=187),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=13.74648, m_value_slope = 1.0635,half_time_min=239),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=13.44168, m_value_slope = 1.0552,half_time_min=305),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=13.13688, m_value_slope = 1.0478,half_time_min=390),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=12.92352, m_value_slope = 1.0414,half_time_min=498),
            BuhlmannCompartment(gf_hi=gf,surfacing_m_value=12.74064, m_value_slope = 1.0359,half_time_min=635)
        ]

    def __calculate_states__(self, dive_profile: DiveProfile):
        for i in range(len(dive_profile.profile)):
            cur_checkpoint = dive_profile.profile[i]  # to update
            if not cur_checkpoint.state:
                if i == 0:
                    cur_checkpoint.state = BuhlmannState(self.compartments)
                else:
                    prev_checkpoint = dive_profile.profile[i-1]
                    cur_checkpoint.state = BuhlmannState(self.compartments, prev_checkpoint, cur_checkpoint)

    def __validate_states__(self, dive_profile: DiveProfile) -> bool:
        for checkpoint in dive_profile:
            if not checkpoint.validation:
                ceilings_valid = all([compartment.ceiling <= checkpoint.depth for compartment in checkpoint.state])
                mod_valid = checkpoint.depth <= checkpoint.gas.mod
                min_od_valid = checkpoint.depth >= checkpoint.gas.min_od
                checkpoint.validation = ceilings_valid and mod_valid and min_od_valid
        return all([checkpoint.validation for checkpoint in dive_profile])

def graph_buhlmann_dive_profile(dive: DiveProfile, buhlmann: Buhlmann_Z16C):
    times = [checkpoint.time/60 for checkpoint in dive.profile]
    gas_ids = list(set([checkpoint.gas.id for checkpoint in dive.profile]))
    gas_ids.sort(key=lambda x: int(x.split(' ')[0].split('/')[0]))
    depths_by_gas = [(gas_id, [(-checkpoint.depth, checkpoint.time) for checkpoint in dive.profile if checkpoint.gas.id == gas_id]) for gas_id in gas_ids]
    depths_by_gas.sort(key=lambda g: g[1][0][1])
    checkpoints_not_allowed = [checkpoint for checkpoint in dive.profile if not checkpoint.validation]
    validation = len(checkpoints_not_allowed) == 0
    min_second_not_allowed = None if validation else int(checkpoints_not_allowed[0].time)
    min_minute_not_allowed = None if validation else int(min_second_not_allowed//60)

    import matplotlib.pyplot as plt
    plt.tight_layout()
    for gas_depths_times in depths_by_gas:
        gas_id = gas_depths_times[0]
        depths_times = gas_depths_times[1]
        for i in range(len(depths_times)-1):
            next_time = depths_times[-i][1]
            prev_time = depths_times[-i-1][1]
            if next_time - prev_time > 60:
                depths_times.insert(-i, [np.nan, np.nan])

        gas_depths = [depth for depth,time in gas_depths_times[1]]
        gas_times = [time/60 for depth,time in gas_depths_times[1]]
        plt.plot(gas_times, gas_depths, label='depth, {}'.format(gas_id))

    for i in range(len(buhlmann.compartments)):
        compartment_ceiling = [-checkpoint.state[i].ceiling for checkpoint in dive.profile]
        plt.plot(times, compartment_ceiling, label=str(buhlmann.compartments[i].half_time_min) + 'min')
        # compartment_ppn2 = [checkpoint.state[i].ppn2 for checkpoint in dive.profile]
        # plt.plot(times, compartment_ppn2, label=str(buhlmann.compartments[i].half_time_min) + 'min')
    

    plot_ndl = False
    for checkpoint in dive.profile:
        mark_ndl_every_mins = 2.5 if max(times)<80 else 5
        if checkpoint.time % (mark_ndl_every_mins*60) == 0:
            ndls = [int(compartment.ndl) for compartment in checkpoint.state]
            # print(ndls)
            ndl = min(ndls)
            # print(ndl)
            ceiling = max([compartment.ceiling for compartment in checkpoint.state])
            if ndl > 0 and checkpoint.time > 0 and not ceiling:
                plt.annotate(ndl,
                        xy=(checkpoint.time/60, 0), xycoords='data',
                        xytext=(0, 0), textcoords='offset points',
                        horizontalalignment='center', verticalalignment='bottom',
                        fontsize=8)
                plot_ndl = True
    if plot_ndl:
        plt.annotate("NDL:",
                xy=(0, 0), xycoords='data',
                xytext=(0, 0), textcoords='offset points',
                horizontalalignment='center', verticalalignment='bottom',
                fontsize=8)

    xcoords = range(int(min(times)), int(max(times)), 5)
    for xc in xcoords:
        plt.axvline(x=xc, color='gray', linestyle='dotted', linewidth='0.3')
    plt.xlabel('time (min)')
    plt.ylabel('depth (m)')
    plt.title(
        'GF {gf_lo}/{gf_hi} Buhlmann ZHL-16C ceilings by compartment\n'.format(gf_lo=buhlmann.gf_lo, gf_hi=buhlmann.gf_hi)
        + 'Dive is {} [DO NOT TRUST THIS PLANNER!]'.format(
            'permissible, {} min'.format(str(int(max(times)))) if validation else 'not permissible from minute {}'.format(min_minute_not_allowed)
            )
        )

    plt.legend(bbox_to_anchor=(1.04, 1), borderaxespad=0)

    plt.savefig('deco.png',bbox_inches="tight")
