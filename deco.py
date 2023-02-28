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

class DiveProfile:
    def __init__(self, checkpoints: List[DiveProfileCheckpoint]) -> None:
        self.__checkpoints__ = checkpoints
        self.profile = self.explode_checkpoints(checkpoints)

    def explode_checkpoints(self, checkpoints):
        return checkpoints

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
    def __init__(self, number, m_values, half_time) -> None:
        self.number = number
        self.m_values = m_values
        self.half_time = half_time

class BuhlmannCompartmentState:
    def __init__(self, compartment, current_checkpoint=None, previous_checkpoint=None) -> None:
        if previous_checkpoint == None:
            self.ppn2 = SURFACE_NITROGEN
        else:
            self.ppn2 = self.update_ppn2(compartment, current_checkpoint, previous_checkpoint)
    
    def update_ppn2(self,
        compartment: BuhlmannCompartment,
        current_checkpoint: DiveProfileCheckpoint,
        previous_checkpoint: DiveProfileCheckpoint):
        # TODO: this is the main algo
        self.ppn2 = SURFACE_NITROGEN

class BuhlmannState(Sequence):
    # this will always be a list of BuhlmannCompartmentState
    # TODO: this is confusing, I want to say that a BuhlmannState is a list of BuhlmannCompartmentState without the attribute
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

class Buhlmann_Z16C(DiveAlgorithm):
    def __init__(self) -> None:
        self.compartments = [BuhlmannCompartment(number=1,m_values = None,half_time=1)]

    def __calculate_states__(self, dive_profile: DiveProfile):
        for i in range(len(dive_profile.profile)):
            cur_checkpoint = dive_profile.profile[i]  # to update
            if i == 0:
                cur_checkpoint.state = BuhlmannState(self.compartments)
            else:
                prev_checkpoint = dive_profile.profile[i-1]
                cur_checkpoint.state = BuhlmannState(self.compartments, prev_checkpoint, cur_checkpoint)

    def __validate_states__(self, dive_profile: DiveProfile) -> bool:
        return None

dive_checkpoints = [
    DiveProfileCheckpoint(time=0, depth=0),
    DiveProfileCheckpoint(time=60, depth=18),
    DiveProfileCheckpoint(time=60*30, depth=18),
    DiveProfileCheckpoint(time=60*(30 + 2), depth=5),
    DiveProfileCheckpoint(time=60*(30 + 2 + 3), depth=5),
    DiveProfileCheckpoint(time=60*(30 + 2 + 3 + 1), depth=0)
    ]

dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann = Buhlmann_Z16C()
buhlmann.process(dive)
