from deco import DiveProfile, Buhlmann_Z16C, graph_buhlmann_dive_profile, DiveProfileCheckpoint, Gas

air = Gas()
air_tec = Gas(ppo2=1.2)
eanx32 = Gas(oxygen=32)
eanx32_tec = Gas(oxygen=32, ppo2=1.2)
eanx36 = Gas(oxygen=36)
eanx36_tec = Gas(oxygen=36, ppo2=1.2)
deco_eanx50 = Gas(oxygen=50, ppo2=1.6)
deco_oxygen = Gas(oxygen=100, ppo2=1.6)
deco_trimix_35_25 = Gas(oxygen=35, helium=25, ppo2=1.6)
deco_trimix_21_35 = Gas(oxygen=21, helium=35, ppo2=1.6)
trimix_21_35 = Gas(oxygen=21, helium=35, ppo2=1.2)
trimix_18_45 = Gas(oxygen=18, helium=45, ppo2=1.2)
trimix_15_55 = Gas(oxygen=15, helium=55, ppo2=1.2)
trimix_12_65 = Gas(oxygen=12, helium=65, ppo2=1.2)
trimix_10_70 = Gas(oxygen=10, helium=70, ppo2=1.2)

rec_gases = [air, eanx32]
tec_bottom_gases=[air_tec, eanx32_tec, eanx36_tec, trimix_21_35, trimix_18_45, trimix_15_55, trimix_12_65, trimix_10_70]
deco_gases = [deco_eanx50, deco_oxygen, deco_trimix_35_25, deco_trimix_21_35]
all_gases = tec_bottom_gases + deco_gases + rec_gases

class ChangeDepth():
    def __init__(self, depth, available_gases=None, time_min=None, time_s=None, speed_mm=9) -> None:
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
            if depth < gas.mod and depth > gas.min_od:
                if not best_gas:
                    best_gas = gas
                else:
                    if best_gas.oxygen < gas.oxygen:
                        best_gas = gas
        if not best_gas:
            raise Exception("no permissible gas for depth {}".format(depth))
        return best_gas

    def get_new_checkpoints(self, dive_checkpoints):
        prev_checkpoint = dive_checkpoints[-1]
        prev_time = prev_checkpoint.time
        prev_depth = prev_checkpoint.depth
        if self.time_s:
            time = prev_time + self.time_s
        elif self.speed_ms:
            time = prev_time + abs(prev_depth - self.depth)/self.speed_ms
            if int(time) != time:
                time = int(time) + 1
        if self.depth > prev_checkpoint.gas.mod and self.available_gases:
            final_gas = self.get_best_gas(self.available_gases, self.depth)  # TODO: allow time for gas switching
            # TODO: this only ever switches halfway through
            intermediate_time = int((prev_time + time)/2)
            intermediate_depth = int((prev_depth + self.depth)/2)
            intermediate_gas = final_gas
            return [
                DiveProfileCheckpoint(time=int(prev_time)+1, depth=prev_depth, gas=prev_checkpoint.gas),
                DiveProfileCheckpoint(time=intermediate_time, depth=intermediate_depth, gas=intermediate_gas),
                DiveProfileCheckpoint(time=time, depth=self.depth, gas=final_gas)
                ]
        else:
            final_gas = prev_checkpoint.gas
            return [DiveProfileCheckpoint(time=time, depth=self.depth, gas=final_gas)]
        

class SwitchGas():
    def __init__(self, gas):
        self.gas = gas
    
    def get_new_checkpoints(self, dive_checkpoints):
        prev_checkpoint = dive_checkpoints[-1]
        return DiveProfileCheckpoint(time=prev_checkpoint.time + 60, depth=prev_checkpoint.depth, gas = self.gas)

class MaintainDepth():
    def __init__(self, time_min=None, time_s=None) -> None:
        if time_min:
            self.time_s = time_min*60
        if time_s:
            self.time_s = time_s
        
    def get_new_checkpoints(self, dive_checkpoints):
        prev_checkpoint = dive_checkpoints[-1]
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
        
    def get_new_checkpoints(self, dive_checkpoints):
        prev_checkpoint = dive_checkpoints[-1]
        checkpoint_1 = ChangeDepth(self.depth, speed_mm=self.speed_ms*60).get_new_checkpoints(dive_checkpoints)
        checkpoint_2 = MaintainDepth(time_s=self.time_s).get_new_checkpoints([*dive_checkpoints, *checkpoint_1])
        return [*checkpoint_1, checkpoint_2]
    
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
    
    def get_new_checkpoints(self, dive_checkpoints):
        prev_checkpoint = dive_checkpoints[-1]
        return ChangeDepth(depth=0, time_s=self.time_s, speed_mm=self.speed_ms*60).get_new_checkpoints(dive_checkpoints)

class GetMeHome():
    def __init__(self, algorithm, available_gases=[air]) -> None:
        self.algorithm = algorithm
        self.available_gases = available_gases
        pass

    @staticmethod
    def get_best_deco_gas(available_gases, new_depth):
        best_gas = None
        for gas in available_gases:
            if new_depth < gas.mod and new_depth > gas.min_od:
                if not best_gas:
                    best_gas = gas
                else:
                    if best_gas.oxygen < gas.oxygen:
                        best_gas = gas
        if not best_gas:
            raise Exception("no permissible gas for depth {}".format(new_depth))
        return best_gas

    def get_new_checkpoints(self, dive_checkpoints):
        dive = DiveProfile(checkpoints=dive_checkpoints)
        count = 0
        while dive_checkpoints[-1].depth > 0 and dive_checkpoints[-1].time < 60*60*10:
            if count % 100 == 0:
                valid = self.algorithm.process(dive)
                if not valid:
                    raise Exception("Dive invalid at minute {}".format(dive_checkpoints[-1].time / 60))
            prev_time = dive_checkpoints[-1].time
            prev_depth = dive_checkpoints[-1].depth
            prev_gas = dive_checkpoints[-1].gas
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
            count = count + 1
        return []  # TODO: make this make sense. right now, it directly modifies the object it takes in


def process_diveplan(dive_plan, initial_gas):
    dive_checkpoints = [DiveProfileCheckpoint(time=0, depth=0, gas=initial_gas)]
    for i in range(len(dive_plan)):
        action = dive_plan[i]
        new_checkpoints = action.get_new_checkpoints(dive_checkpoints)
        if type(new_checkpoints) == list:
            dive_checkpoints.extend(new_checkpoints)
        else:
            dive_checkpoints.append(new_checkpoints)
    return dive_checkpoints

buhlmann = Buhlmann_Z16C(gf=100)

# dive_plan = [
#     SwitchGas(gas=air),
#     ChangeDepth(depth=45, speed_mm=18, available_gases=[air]),
#     MaintainDepth(time_min=16),
#     # ChangeDepth(depth=25, speed_mm=4, available_gases=[air]),
#     # MaintainDepth(time_min=4),
#     # ChangeDepth(depth=22, time_min=2, available_gases=[air]),
#     # SwitchGas(gas=trimix_12_65),
#     # ChangeDepth(depth=65, speed_mm=18, available_gases=available_gases),
#     # ChangeDepth(depth=55, available_gases=[air], speed_mm=18),
#     # SwitchGas(gas=trimix_12_65),
#     # MaintainDepth(time_min=28),
#     # ChangeDepth(depth=18, time_min=3, available_gases=[air]),
#     # MaintainDepth(time_min=29),
#     GetMeHome(algorithm=buhlmann, available_gases=[air])
#     # SafetyStop(),
#     # AscendDirectly()
# ]

def make_dive_actions_from_list(l, s=20):
    return [*[ChangeDepth(depth=d, time_s=s, available_gases=tec_bottom_gases) for d in l], GetMeHome(algorithm=buhlmann, available_gases=tec_bottom_gases + deco_gases)]

simons_reef = [
    5.2,9.2,12.6,14.9,15.5,16.6,16.6,16.9,18.4,19.3,20,22.3,24.9,26.4,26.3,27,27.6,29,
    29.4,29.5,29.8,29.2,29,28.9,28.4,27.8,26.6,26.6,26.6,26.6,26.8,26.6,26.5,26.2,25.7,
    26.8,27,27.1,27.7,27.9,27.3,27.7,28.5,28.2,26.8,26.7,26,25.2,24.2,23.3,22.9,22.3,
    22.2,21.9,21.8,21.7,21.2,21.9,22.3,23,23.4,23,23.2,23.8,23.6,23,23,22.8,23.1,23.2,
    23.2,23.1,23,21.7,20.8,20.1,19.6,19.4,19.6,19.3,19.1,18,17.9,17.2,15.3,15.3,14.6,
    14.4,14.3,14.6,14.9,14.2,11.9,9.6,7.1,6.5,6.6,5.9,5.7,5.2,4.6,6,6.1,5.1,5.6,5.8,
    4.4,3.2,2.4
]

rashi_halik = [
    4.4,6.8,11.4,15.6,20.6,25.6,29.4,31.1,30,29.2,28.6,28.2,27.5,27,26.8,26.3,25.1,
    24.7,24.4,23.5,24,24.4,24.7,26.3,26.6,26.4,25.4,25.2,26,27.3,28,28.3,28.6,28.7,
    28.7,27.7,27.2,26.5,26.8,26.8,26.4,26,25.9,25.4,26.2,26.6,26.6,26.8,26.3,26.7,
    26.5,26.3,25.8,25.8,26.2,25.6,25.3,25.5,26.2,26.9,26.8,26.7,25.4,26.1,26.1,25.6,
    25,24.6,23.8,23.7,22.4,20.8,19.1,18,16.6,14.9,13.5,14,14.1,14.5,14.4,14.3,14.9,
    15.3,15.5,15,14.7,14.4,14.5,14.8,15,15.1,14.6,14.5,14.3,13.8,13.7,13.6,13.2,13,
    13.3,13.4,13.6,13.8,14.2,14.3,14.2,14.6,14,13.4,13.1,12.6,12.8,13.1,13.2,13.7,
    13.5,13.3,13.2,12.3,11.8,10.9,8.5,7,6.5,6.6,6.5,6.3,6.3,5.7,5.7,5.6,5.5,5.3,5.4,
    5.9,5.5,5.6,5.3,5.1,5.4,4.8,4,3.6,2.8
]
dive_plan = make_dive_actions_from_list(rashi_halik)

dive_checkpoints = process_diveplan(dive_plan, air)
dive = DiveProfile(checkpoints=dive_checkpoints)
buhlmann.process(dive)
graph_buhlmann_dive_profile(dive, buhlmann)
