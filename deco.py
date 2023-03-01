from abc import ABC
from typing import List, Sequence

"""
Assumptions:

Only breathing air.
Input is a list of tuples (time, depth)  - starting at (0,0) and ending at (T, 0) for T>0
This will be converted to a second-by-second list of (time,depth)
An algorithm will then run to generate (time,depth,compartment_1_ppN2)
A second algorithm will compare (depth,compartment_1_ppN2) to the M-value at that depth
"""

# set obvious parameters
OXYGEN = 0.21
NITROGEN = 0.79
assert OXYGEN + NITROGEN == 1

SURFACE_OXYGEN = 0.21
SURFACE_NITROGEN = 0.79
assert SURFACE_OXYGEN + SURFACE_NITROGEN == 1

class DiveProfileCheckpoint:
    def __init__(self, time, depth, state=None, validation=None) -> None:
        self.time = time
        self.depth = depth
        self.state = state
        self.validation = validation

    def __repr__(self) -> str:
        return str((self.time, self.depth, self.state, self.validation))
    
    def __str__(self):
        return str((self.time, self.depth, self.state, self.validation))

class DiveProfile:
    def __init__(self, checkpoints: List[DiveProfileCheckpoint]) -> None:
        self.__checkpoints__ = checkpoints
        self.profile = self.explode_checkpoints(checkpoints)

    def explode_checkpoints(self, checkpoints):
        assert checkpoints[0].time == 0
        assert checkpoints[0].depth == 0
        profile = []
        time_to_process = 0
        while time_to_process <= checkpoints[-1].time:
            # get previous and next checkpoint
            if time_to_process in [checkpoint.time for checkpoint in checkpoints]:
                for checkpoint in checkpoints:
                    if checkpoint.time == time_to_process:
                        profile.append(checkpoint)
            else:
                for i in range(len(checkpoints)-1):
                    prev_checkpoint = checkpoints[i]
                    next_checkpoint = checkpoints[i+1]
                    if time_to_process > prev_checkpoint.time and time_to_process < next_checkpoint.time:
                        break
                prop_prev = (time_to_process - prev_checkpoint.time) / (next_checkpoint.time - prev_checkpoint.time)
                interpolated_depth = next_checkpoint.depth * prop_prev + prev_checkpoint.depth * (1-prop_prev)
                new_checkpoint = DiveProfileCheckpoint(time=time_to_process, depth=interpolated_depth)
                profile.append(new_checkpoint)
            time_to_process = time_to_process + 1
        return profile
    
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
    def __init__(self, number, surfacing_m_value, m_value_slope, half_time_min) -> None:
        self.number = number  # unused
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
        if previous_checkpoint == None:
            self.ppn2 = SURFACE_NITROGEN
            self.ceiling = self.calculate_ceiling(self.ppn2, compartment.surfacing_m_value, compartment.m_value_slope)
        else:
            prev_ppn2 = [
                bcs.ppn2 for bcs in previous_checkpoint.state if compartment == bcs.compartment  # note the object comparison
                ][0]
            self.update_ppn2(
                compartment,
                inhaled_ppn2=(1+(current_checkpoint.depth)/10) * NITROGEN,
                time_spent=current_checkpoint.time - previous_checkpoint.time,
                prev_ppn2=prev_ppn2
            )
            self.ceiling = self.calculate_ceiling(self.ppn2, compartment.surfacing_m_value, compartment.m_value_slope)
    
    def update_ppn2(self,
        compartment: BuhlmannCompartment,
        inhaled_ppn2,
        time_spent,
        prev_ppn2
        ):
        # this is the main algo
        self.ppn2 = prev_ppn2 + (inhaled_ppn2 - prev_ppn2) * (1 - 2 ** (-(time_spent / 60) / compartment.half_time_min))

    def calculate_ceiling(self, ppn2, surfacing_m_value, m_value_slope):#, gf=100):
        # TODO stare carefully at this maths as this whole section makes NO sense
        surfacing_m_value_bar = surfacing_m_value/10 # body partial pressure limit for nitrogen
        # gf_prop = gf/100
        # equiv_abs_pressure = ppn2  # depth at which you would be in equilibrium. this is the y-axis
        # m_value_slope is increase of M per metre depth - the units here are different - change in partial pressure per metre
        m_value_slope_bar = m_value_slope  # change in partial pressure per bar
        # adjusted_m_value_slope = m_value_slope*(gf_prop) + (1-gf_prop)  # weighted average of M-value slope and equilibrium

        """
        The Nitrogen constant NITROGEN should not appear here AT ALL. nobody cares what you're breathing. It's only the ppn2
        in your body compared to the pressure around you. That's all

        Find M-value for a given ambient pressure.

        Ambient pressure = 1 means M-value = surfacing_m_value
        Ambient pressure = 2 means M-value = surfacing_m_value + m_value_slope_bar

        so M_value = surfacing_m_value + amb_press_bar * m_value_slope_bar

        now sub ppn2 = M_value and find amb_press_bar

        amb_press_bar = (ppn2 - surfacing_m_value) / m_value_slope_bar
        """

        ceiling_bar = (ppn2 - surfacing_m_value_bar) / m_value_slope_bar
        ceiling = ceiling_bar*10  # why not +1 ?!
        if ceiling<0:
            return 0
        else:
            return ceiling

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
    def __init__(self) -> None:
        # https://www.shearwater.com/wp-content/uploads/2019/05/understanding_m-values.pdf
        self.compartments = [
            BuhlmannCompartment(number=1,surfacing_m_value=29.65704, m_value_slope = 1.7928,half_time_min=5),
            BuhlmannCompartment(number=2,surfacing_m_value=25.35936, m_value_slope = 1.5352,half_time_min=8),
            BuhlmannCompartment(number=3,surfacing_m_value=22.49424, m_value_slope = 1.3847,half_time_min=12.5),
            BuhlmannCompartment(number=4,surfacing_m_value=20.36064, m_value_slope = 1.278,half_time_min=18.5),
            BuhlmannCompartment(number=5,surfacing_m_value=18.53184, m_value_slope = 1.2306,half_time_min=27),
            BuhlmannCompartment(number=6,surfacing_m_value=16.94688, m_value_slope = 1.1857,half_time_min=38.3),
            BuhlmannCompartment(number=7,surfacing_m_value=15.94104, m_value_slope = 1.1504,half_time_min=54.3),
            BuhlmannCompartment(number=8,surfacing_m_value=15.27048, m_value_slope = 1.1223,half_time_min=77),
            BuhlmannCompartment(number=9,surfacing_m_value=14.7828, m_value_slope = 1.0999,half_time_min=109),
            BuhlmannCompartment(number=10,surfacing_m_value=14.38656, m_value_slope = 1.0844,half_time_min=146),
            BuhlmannCompartment(number=11,surfacing_m_value=14.05128, m_value_slope = 1.0731,half_time_min=187),
            BuhlmannCompartment(number=12,surfacing_m_value=13.74648, m_value_slope = 1.0635,half_time_min=239),
            BuhlmannCompartment(number=13,surfacing_m_value=13.44168, m_value_slope = 1.0552,half_time_min=305),
            BuhlmannCompartment(number=14,surfacing_m_value=13.13688, m_value_slope = 1.0478,half_time_min=390),
            BuhlmannCompartment(number=15,surfacing_m_value=12.92352, m_value_slope = 1.0414,half_time_min=498),
            BuhlmannCompartment(number=16,surfacing_m_value=12.74064, m_value_slope = 1.0359,half_time_min=635)
        ]

    def __calculate_states__(self, dive_profile: DiveProfile):
        for i in range(len(dive_profile.profile)):
            cur_checkpoint = dive_profile.profile[i]  # to update
            if i == 0:
                cur_checkpoint.state = BuhlmannState(self.compartments)
            else:
                prev_checkpoint = dive_profile.profile[i-1]
                cur_checkpoint.state = BuhlmannState(self.compartments, prev_checkpoint, cur_checkpoint)

    def __validate_states__(self, dive_profile: DiveProfile) -> bool:
        for checkpoint in dive_profile:
            checkpoint.validation = all([compartment.ceiling <= checkpoint.depth for compartment in checkpoint.state])

def graph_buhlmann_dive_profile(dive: DiveProfile, buhlmann: Buhlmann_Z16C):
    times = [checkpoint.time/60 for checkpoint in dive.profile]
    depths = [-checkpoint.depth for checkpoint in dive.profile]
    checkpoints_not_allowed = [checkpoint for checkpoint in dive.profile if not checkpoint.validation]
    validation = len(checkpoints_not_allowed) == 0
    min_minute_not_allowed = None if validation else checkpoints_not_allowed[0].time//60

    import matplotlib.pyplot as plt
    import numpy as np
    plt.tight_layout()
    plt.plot(times, depths, label='depth')

    for i in range(len(buhlmann.compartments)):
        compartment_ceiling = [-checkpoint.state[i].ceiling for checkpoint in dive.profile]
        plt.plot(times, compartment_ceiling, label=str(buhlmann.compartments[i].half_time_min) + 'min')
        # compartment_ppn2 = [checkpoint.state[i].ppn2 for checkpoint in dive.profile]
        # plt.plot(times, compartment_ppn2, label=str(buhlmann.compartments[i].half_time_min) + 'min')
    plt.xlabel('time (min)')
    plt.ylabel('depth (m)')
    plt.title('Naive (GF 100/100) Buhlmann ZHL-16C ceilings by compartment\nDive is {} [DO NOT TRUST THIS PLANNER!]'.format('permissible' if validation else 'not permissible from minute {}'.format(min_minute_not_allowed)))

    # Put a legend to the right of the current axis
    # plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.legend(loc='center left')

    plt.savefig('deco.png')

def lazy_make_dive_checkpoints(l):
    checkpoints = []
    t = 0
    for i in l:
        checkpoints.append(DiveProfileCheckpoint(time=i[0]*60+t, depth=i[1]))
        t += i[0]*60
    return checkpoints

dive_checkpoints = lazy_make_dive_checkpoints([
    (0,0),
    (1,35),
    (30,35),
    (3,5),
    (3,5),
    (1,0)
])

dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann = Buhlmann_Z16C()
buhlmann.process(dive)
graph_buhlmann_dive_profile(dive, buhlmann)
