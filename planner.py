from deco import DiveProfile, Buhlmann_Z16C, graph_buhlmann_dive_profile, DiveProfileCheckpoint

class ChangeDepth():
    def __init__(self, depth, time_min=None, time_s=None, speed_mm=9) -> None:
        self.depth = depth
        if time_min:
            self.time_s = time_min*60
            self.speed_ms = None
        elif time_s:
            self.time_s = time_s
            self.speed_ms = None
        else:
            self.time_s = None
        self.speed_ms = speed_mm/60
        
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        prev_time = prev_checkpoint.time
        prev_depth = prev_checkpoint.depth
        if self.time_s:
            time = prev_time + self.time_s
        elif self.speed_ms:
            time = prev_time + abs(prev_depth - self.depth)/self.speed_ms
        return DiveProfileCheckpoint(time=time, depth=self.depth)

class MaintainDepth():
    def __init__(self, time_min=None, time_s=None) -> None:
        if time_min:
            self.time_s = time_min*60
        if time_s:
            self.time_s = time_s
        
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        prev_time = prev_checkpoint.time
        prev_depth = prev_checkpoint.depth
        return DiveProfileCheckpoint(time=self.time_s+prev_time, depth=prev_depth)

class SafetyStop():
    def __init__(self, depth=5, ss_time_min=3, ss_time_s=None, speed_mm=9) -> None:
        self.depth = depth
        if ss_time_min:
            self.time_s = ss_time_min*60
        elif ss_time_s:
            self.time_s = ss_time_s
        self.speed_ms = speed_mm/60
        
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        checkpoint_1 = ChangeDepth(self.depth, speed_mm=self.speed_ms*60).get_new_checkpoint(prev_checkpoint)
        checkpoint_2 = MaintainDepth(time_s=self.time_s).get_new_checkpoint(checkpoint_1)
        return [checkpoint_1, checkpoint_2]
    
class AscendDirectly():
    def __init__(self, time_min=None, time_s=None, speed_mm=9) -> None:
        if time_min:
            self.time_s = time_min*60
            self.speed_ms = None
        elif time_s:
            self.time_s = time_s
            self.speed_ms = None
        else:
            self.time_s = None
        self.speed_ms = speed_mm/60
    
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        return ChangeDepth(depth=0, time_s=self.time_s, speed_mm=self.speed_ms*60).get_new_checkpoint(prev_checkpoint)

class GetMeHome():
    def __init__(self) -> None:
        # TODO: this would be really cool, if a little tricky.
        # Iteratively calculate dive plans using ANY algo and the validate() function, changing depths only to multiples of 3
        pass

def process_diveplan(dive_plan):
    dive_checkpoints = [DiveProfileCheckpoint(time=0, depth=0)]
    for i in range(len(dive_plan)):
        prev_checkpoint = dive_checkpoints[-1]
        action = dive_plan[i]
        new_checkpoint = action.get_new_checkpoint(prev_checkpoint)
        if type(new_checkpoint) == list:
            dive_checkpoints.extend(new_checkpoint)
        else:
            dive_checkpoints.append(new_checkpoint)
    return dive_checkpoints


dive_plan = [
    ChangeDepth(depth=30, time_min=2),
    MaintainDepth(time_min=30),
    SafetyStop(),
    AscendDirectly()
]

dive_checkpoints = process_diveplan(dive_plan)
dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann = Buhlmann_Z16C(gf=100)
buhlmann.process(dive)
graph_buhlmann_dive_profile(dive, buhlmann)
