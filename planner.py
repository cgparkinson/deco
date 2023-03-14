from deco import DiveProfile, Buhlmann_Z16C, graph_buhlmann_dive_profile, DiveProfileCheckpoint, Gas

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

class ChangeDepth():
    def __init__(self, depth, available_gases, time_min=None, time_s=None, speed_mm=9) -> None:
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
        self.available_gases = available_gases
    
    @staticmethod
    def get_best_gas(available_gases, depth):
        best_gas = None
        for gas in available_gases:
            if depth < gas.mod:
                if not best_gas:
                    best_gas = gas
                else:
                    if best_gas.oxygen < gas.oxygen:
                        best_gas = gas
        if not best_gas:
            raise Exception("no permissible gas for depth {}".format(depth))
        return best_gas

    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        prev_time = prev_checkpoint.time
        prev_depth = prev_checkpoint.depth
        if self.depth > prev_checkpoint.gas.mod:
            gas = self.get_best_gas(self.available_gases, self.depth)  # TODO: allow time for gas switching and FIXME doesnt work!!
        else:
            gas = prev_checkpoint.gas
        if self.time_s:
            time = prev_time + self.time_s
        elif self.speed_ms:
            time = prev_time + abs(prev_depth - self.depth)/self.speed_ms
        return DiveProfileCheckpoint(time=int(time)+1, depth=self.depth, gas=gas)

class SwitchGas():
    def __init__(self, gas):
        self.gas = gas
    
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        return DiveProfileCheckpoint(time=prev_checkpoint.time + 60, depth=prev_checkpoint.depth, gas = self.gas)

class MaintainDepth():
    def __init__(self, time_min=None, time_s=None) -> None:
        if time_min:
            self.time_s = time_min*60
        if time_s:
            self.time_s = time_s
        
    def get_new_checkpoint(self, prev_checkpoint: DiveProfileCheckpoint):
        prev_time = prev_checkpoint.time
        prev_depth = prev_checkpoint.depth
        prev_gas = prev_checkpoint.gas
        return DiveProfileCheckpoint(time=self.time_s+int(prev_time), depth=prev_depth, gas=prev_gas)

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
    def __init__(self, algorithm, available_gases=[air]) -> None:
        self.algorithm = algorithm
        self.available_gases = available_gases
        pass

    @staticmethod
    def get_best_deco_gas(available_gases, new_depth):
        best_gas = None
        for gas in available_gases:
            if new_depth < gas.mod:
                if not best_gas:
                    best_gas = gas
                else:
                    if best_gas.oxygen < gas.oxygen:
                        best_gas = gas
        if not best_gas:
            raise Exception("no permissible gas for depth {}".format(new_depth))
        return best_gas

    def get_new_checkpoint_from_all_checkpoints(self, dive_checkpoints):
        dive = DiveProfile(checkpoints=dive_checkpoints)
        while dive_checkpoints[-1].depth > 0 and dive_checkpoints[-1].time < 60*60:
            prev_time = dive_checkpoints[-1].time
            prev_depth = dive_checkpoints[-1].depth
            prev_gas = dive_checkpoints[-1].gas
            print(prev_gas.id)
            if prev_depth % 3 == 0:
                new_depth = prev_depth - 3
            else:
                new_depth = prev_depth // 3 * 3
            if prev_time % 1 == 0:
                new_time = prev_time + 20
            else:
                new_time = int(prev_time)+1
            new_gas = self.get_best_deco_gas(self.available_gases, new_depth)  # TODO: only switch gas during a stop
            new_dive_checkpoint = DiveProfileCheckpoint(time=new_time, depth = new_depth, gas=new_gas)
            dive_checkpoints.append(new_dive_checkpoint)
            dive.add_checkpoint(new_dive_checkpoint)
            valid = self.algorithm.process(dive)
            if not valid:
                new_dive_checkpoint = DiveProfileCheckpoint(time=prev_time+60, depth = prev_depth, gas=prev_gas)
                dive_checkpoints.pop()
                dive_checkpoints.append(new_dive_checkpoint)
                dive.delete_after(prev_time)
                dive.add_checkpoint(new_dive_checkpoint)
        
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

buhlmann = Buhlmann_Z16C(gf=80)
available_gases=[air, deco_eanx50, deco_oxygen, trimix_12_65, trimix_15_55, trimix_18_45]
dive_plan = [
    # ChangeDepth(depth=55, speed_mm=18, available_gases=available_gases),
    # SwitchGas(gas=trimix_12_65),
    # ChangeDepth(depth=65, speed_mm=18, available_gases=available_gases),
    ChangeDepth(depth=45, available_gases=[air], speed_mm=18),
    MaintainDepth(time_min=20),
    GetMeHome(algorithm=buhlmann, available_gases=available_gases)
    # SafetyStop(),
    # AscendDirectly()
]

dive_checkpoints = process_diveplan(dive_plan)
dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann.process(dive)
graph_buhlmann_dive_profile(dive, buhlmann)
