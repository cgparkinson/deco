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
    def __init__(self, algorithm) -> None:
        self.algorithm = algorithm
        pass

    def get_new_checkpoint_from_all_checkpoints(self, dive_checkpoints):
        # TODO: make it so we don't have to calculate the whole status each iteration, we should cache it
        while dive_checkpoints[-1].depth > 0 and dive_checkpoints[-1].time < 10000:
            prev_time = dive_checkpoints[-1].time
            prev_depth = dive_checkpoints[-1].depth
            if prev_depth % 3 == 0:
                new_depth = prev_depth - 3
            else:
                new_depth = prev_depth // 3 * 3
            if prev_time % 1 == 0:
                new_time = prev_time + 20
            else:
                new_time = int(prev_time)+1
            
            new_dive_checkpoint = DiveProfileCheckpoint(time=new_time, depth = new_depth)
            dive_checkpoints.append(new_dive_checkpoint)
            dive = DiveProfile(checkpoints=dive_checkpoints)
            valid = self.algorithm.process(dive)
            if not valid:
                dive_checkpoints.pop()
                dive_checkpoints.append(DiveProfileCheckpoint(time=prev_time+60, depth = prev_depth))
            print(new_time, new_depth)
        
        return dive_checkpoints

def process_diveplan(dive_plan):
    dive_checkpoints = [DiveProfileCheckpoint(time=0, depth=0)]
    for i in range(len(dive_plan)):
        prev_checkpoint = dive_checkpoints[-1]
        action = dive_plan[i]
        try:  # UGLY
            new_checkpoint = action.get_new_checkpoint(prev_checkpoint)
            if type(new_checkpoint) == list:
                dive_checkpoints.extend(new_checkpoint)
            else:
                dive_checkpoints.append(new_checkpoint)
        except:
            dive_checkpoints = action.get_new_checkpoint_from_all_checkpoints(dive_checkpoints)
    return dive_checkpoints

buhlmann = Buhlmann_Z16C(gf=75)

dive_plan = [
    ChangeDepth(depth=45, speed_mm=18),
    MaintainDepth(time_min=20.2),
    GetMeHome(algorithm=buhlmann)
    # SafetyStop(),
    # AscendDirectly()
]

dive_checkpoints = process_diveplan(dive_plan)
dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann.process(dive)
graph_buhlmann_dive_profile(dive, buhlmann)
