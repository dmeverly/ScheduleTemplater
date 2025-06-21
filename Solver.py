import numpy as np
import random
from helpers import (
    weekdays,
    ScheduleBalancer,
    validStaffConstraint,
    constraintType,
    Employee,
)

ABS_PENALTY = 10000
EPOCH_LIMIT = 1000
SHIFTLENGTH = 12  # hours

class Solver:
    def __init__(self, balancer: ScheduleBalancer, daypool: list[Employee],
                 nightpool: list[Employee], floatpool: list[Employee], unfilled: Employee):
        self.balancer = balancer
        self.state = balancer.state
        self.dayPool = daypool
        self.nightPool = nightpool
        self.floatPool = floatpool
        self.unfilled = unfilled
        self.allPool = list({*daypool, *nightpool, *floatpool})

        self.hours_used = self._calculate_hours_used(self.state)
        self.current_score = self.score(self.state)
        self.lastRejected = None

        # Annealing parameters
        self.temperature = 1000.0
        self.cooling_rate = 0.9999

    # dict table of hours used per pay for each employee, used to check valid assignments
    def _calculate_hours_used(self, schedule: np.ndarray) -> dict:
        hours = {w: {emp: 0 for emp in self.allPool} for w in range(schedule.shape[0])}
        W, D, S = schedule.shape
        for w in range(W):
            for d in range(D):
                for s in range(S):
                    emp = schedule[w, d, s]
                    if emp is not self.unfilled:
                        hours[w][emp] += SHIFTLENGTH
        return hours
    
    # find most appropriate employee to fill a slot
    def _select_employee_for_slot(self, schedule, w, d, s, hours_map):
        best_candidate = self.unfilled
        best_delta = float('inf')

        original_emp = schedule[w, d, s]

        for emp in self.allPool:
            if emp is self.unfilled:
                continue

            # Skip if already working this day
            if emp in schedule[w, d, :]:
                continue

            # No day after night
            if s in (0, 1):
                if (d > 0 and schedule[w, d - 1, 2] is emp) or (d == 0 and w > 0 and schedule[w - 1, 6, 2] is emp):
                    continue

            # Check hours cap
            cap = next(c.val for c in emp.getConstraints()
                    if c.name == validStaffConstraint.HOURS_PER_PAY_PERIOD.value)
            pp_start = 2 * (w // 2)
            used = sum(
                SHIFTLENGTH
                for w2 in (pp_start, pp_start + 1) if w2 < schedule.shape[0]
                for d2 in range(schedule.shape[1])
                for s2 in range(schedule.shape[2])
                if schedule[w2, d2, s2] is emp
            )
            if used + SHIFTLENGTH > cap:
                continue

            # Tentatively assign
            schedule[w, d, s] = emp

            # Check hard violations
            if any(not c.isSatisfied(schedule, w, d, s) and c.ctype == constraintType.ABSOLUTE
                for c in emp.getConstraints()):
                schedule[w, d, s] = original_emp
                continue

            # Compute score delta
            trial_score = self.score(schedule)
            schedule[w, d, s] = original_emp
            delta = trial_score - self.current_score
            #print(f"Trying {emp.name} at {w}{d}{s} → ΔScore={delta}")

            # Favor lowest delta
            if delta < best_delta:
                best_candidate = emp
                #print(f'selected {best_candidate}')
                best_delta = delta
            elif delta == best_delta:
                # Tiebreak: prefer less-used employee
                if hours_map[w].get(emp, 0) < hours_map[w].get(best_candidate, 9999):
                    best_candidate = emp

        #print(f"Selected {best_candidate.name} at {w}{d}{s} → ΔScore={best_delta}")
        return best_candidate


    # cost function for assigning employee with least number of relative conflicts
    def _soft_cost_eval(self, schedule, w, d, s, emp):
        orig = schedule[w, d, s]

        # temp assignment for constraint checking
        schedule[w, d, s] = emp
        cost = 0
        for c in emp.getConstraints():
            if c.ctype == constraintType.RELATIVE and c.name != validStaffConstraint.MINIMUM_HOURS.value:
                if not c.isSatisfied(schedule, w, d, s):
                    cost += 2
        # adjacency bonus - bias toward working stretches of days   -- can add a check against the length of consecutive days constraint per employee --
        if (d > 0 and emp in schedule[w, d-1, :]) or (d < schedule.shape[1]-1 and emp in schedule[w, d+1, :]):
            max_consec = next(
                (c.val for c in emp.getConstraints()
                if c.name == validStaffConstraint.CONSECUTIVE_DAYS.value),
                None
            )

            if max_consec is not None:
                # 2) compute run length before this day
                prev_run = 0
                dd = d-1
                while dd >= 0 and any(schedule[w, dd, s] is emp for s in range(3)):
                    prev_run += 1
                    dd -= 1

                # 3) compute run length after this day
                next_run = 0
                dd = d+1
                D = schedule.shape[1]
                while dd < D and any(schedule[w, dd, s] is emp for s in range(3)):
                    next_run += 1
                    dd += 1

                # total run if we add them today
                total_run = prev_run + 1 + next_run

                # 4) only give the bonus if we stay within their limit
                if total_run <= max_consec:
                    cost -= 3  # or whatever your bonus is

        # reverse temp assignment
        schedule[w, d, s] = orig
        return cost

    # rank open slots by most constrained -> least constrained
    # priority given to d1 and n shifts, then d2 on monday, wed, thurs only
    def slot_order(self):
        ORDER   = {0: 0, 2: 1, 1: 2}
        DAY_PRI = {
            weekdays.Thursday.value: 0,
            weekdays.Wednesday.value: 1,
            weekdays.Monday.value: 2
        }
        slots = []
        W, D, S = self.state.shape
        for w in range(W):
            for d in range(D):
                if d in (weekdays.Saturday.value, weekdays.Sunday.value):
                    continue
                for s in (0, 2, 1):
                    if d in (weekdays.Tuesday.value, weekdays.Friday.value) and s == 1:
                        continue
                    hard_ok = 0
                    soft_violations = {}
                    for emp in self.allPool:
                        if emp is self.unfilled or emp in self.state[w, d, :]:
                            continue
                        # no day-after-night
                        if s in (0,1):
                            prev = (d > 0 and self.state[w, d-1, 2] is emp) or \
                                   (d == 0 and w > 0 and self.state[w-1, 6, 2] is emp)
                            if prev:
                                continue
                        # absolute constraints
                        orig = self.state[w, d, s]
                        self.state[w, d, s] = emp
                        abs_violate = any(
                            not c.isSatisfied(self.state, w, d, s)
                            for c in emp.getConstraints()
                            if c.ctype == constraintType.ABSOLUTE
                        )
                        self.state[w, d, s] = orig
                        if abs_violate:
                            continue
                        hard_ok += 1
                        soft_violations[emp] = sum(
                            not c.isSatisfied(self.state, w, d, s)
                            for c in emp.getConstraints()
                            if c.ctype == constraintType.RELATIVE
                        )
                    pr = ORDER[s]*10 + DAY_PRI.get(d, 3)
                    slots.append(((w, d, s), hard_ok, pr, soft_violations))

        slots.sort(key=lambda item: (
            item[1],       # fewest hard_ok
            item[2],       # priority
            min(item[3].values()) if item[3] else float('inf')
        ))

        choiceList = [t[0] for t in slots]
        return choiceList

    # propose the most appropriate move into most constrained slot
    def propose_move(self):

        #list of available slots sorted by level of constraint
        choices = self.slot_order()
        if self.lastRejected:
            choices = [c for c in choices if c != self.lastRejected] + [self.lastRejected]

        for (w, d, s) in choices:
            if self.state[w, d, s] is not self.unfilled:
                continue
            trial_state = self.state.copy()
            trial_hours = self.hours_used.copy()
            orig = trial_state[w, d, s]
            if orig is not self.unfilled:
                trial_hours[w][orig] -= SHIFTLENGTH

            candidate = self._select_employee_for_slot(trial_state, w, d, s, trial_hours)
            if candidate is not self.unfilled:
                trial_state[w, d, s] = candidate
                trial_hours[w][candidate] += SHIFTLENGTH
                self.lastRejected = (w, d, s)
                return trial_state, trial_hours

        self.lastRejected = choices[-1]
        return None, None

    # score constraint violations and unfilled shifts +1 for each relative violation and +5 for each unfilled shift, + ABS_PENALTY for absolute violations
    def score(self, schedule):
        g_abs, g_rel, s_abs, s_rel = self.balancer.isValidSchedule(False, schedule)
        # penalize unfilled
        W, D, S = schedule.shape
        for w in range(W):
            for d in range(7):
                downstaff = d in (weekdays.Saturday.value, weekdays.Sunday.value,
                                  weekdays.Tuesday.value, weekdays.Friday.value)
                for s in range(3):
                    if downstaff and s == 1:
                        continue
                    if schedule[w, d, s].name == "UNFILLED":
                        g_abs += 5
        return (g_abs + s_abs) * ABS_PENALTY + g_rel + s_rel

    # agent driver, fills initial schedule by greedy best search on most constrained variables
    # after schedule is full, searches to minimize cost by filling vacant shifts and looking for valid swaps
    # finally, searches for underworked employees and attempts to find slot to place them in
    def run_annealing(self):
        print("Starting greedy initialization...")
        
        choices = self.slot_order()
        for (w, d, s) in choices:
            if self.state[w, d, s] is self.unfilled:
                emp = self._select_employee_for_slot(self.state, w, d, s, self.hours_used)
                if emp is not self.unfilled:
                    self.state[w, d, s] = emp
                    self.hours_used[w][emp] += SHIFTLENGTH
                    
        best_state = self.state.copy()
        best_score = self.current_score
        history_epochs, history_scores = [], []
        epoch = 0

        while epoch < EPOCH_LIMIT and best_score > 0:
            choices = self.slot_order()
            epoch += 1
            print(f"Epoch {epoch}, current score: {self.current_score}")
            self.temperature *= self.cooling_rate
            if self.temperature < 1e-4:
                print("Temperature too low, stopping annealing.")
                break
            
            # propose move into slot
            new_state, h_map = self.propose_move()
            if new_state is None:
                break
            new_score = self.score(new_state)
            delta = new_score - self.current_score

            # if score is better, take it. Otherwise, randomly take by simulated annealing
            if delta < 0 or random.random() < np.exp(-delta / self.temperature):
                self.state, self.hours_used, self.current_score = new_state, h_map, new_score
                self.lastRejected = None

            if self.current_score < best_score:
                best_state, best_score = self.state.copy(), self.current_score
                best_hours = self.hours_used

            history_epochs.append(epoch)
            history_scores.append(self.current_score)

        # print post-annealing, pre-repair
        print("Starting post‑annealing repair…")
        
        self.state, self.current_score = best_state, best_score
        self.balancer.state = self.state
        print(f"Greedy best state\n{self.balancer}")
        self.balancer.isValidSchedule(printMode=True)

        # repair phase
        self.state, history_epochs, history_scores = self.repair_schedule(history_epochs, history_scores)
        self.current_score = self.score(self.state)
        self.balancer.state = self.state

        # print post-repair
        print(f"After Repair state\n{self.balancer}")
        self.balancer.isValidSchedule(printMode=True)

        # final score, return for graphing
        print("Template complete. Score =", self.current_score)
        return self.state, self.current_score, history_epochs, history_scores

    # find violations in completed schedule and the best employee to fill them
    def repair_schedule(self, history_epochs, history_score, max_iters=1000):
        def find_violations():
            vio = []
            W, D, S = self.state.shape
            for w in range(W):
                for d in range(D):
                    for s in range(S):
                        emp = self.state[w, d, s]
                        if emp is self.unfilled:
                            continue
                        for c in emp.getConstraints():
                            if not c.isSatisfied(self.state, w, d, s):
                                vio.append((emp, c, w, d, s))
            # global holes
            for w in range(W):
                for d in range(D):
                    for s in range(S):
                        if self.state[w, d, s] is self.unfilled:
                            for gc in self.balancer.constraints:
                                if gc.ctype == constraintType.ABSOLUTE and not gc.isSatisfied(self.state, w, d, s):
                                    vio.append((self.unfilled, gc, w, d, s))
                                    break
            return vio

        iters = 0
        improved = True
        W, D, S = self.state.shape

        while improved and iters < max_iters:
            iters += 1
            history_epochs.append(len(history_epochs)+1)
            history_score.append(self.current_score)
            improved = False
            current_score = self.score(self.state)
            violations = find_violations()

            # one entry per slot
            seen = set()
            slot_vio = []
            for emp, c, w, d, s in violations:
                if (w, d, s) not in seen:
                    seen.add((w, d, s))
                    slot_vio.append((emp, w, d, s))

            for emp, w, d, s in slot_vio:
                if emp is self.unfilled:
                    # try fill hole
                    cand = self._select_employee_for_slot(self.state, w, d, s, self.hours_used)
                    if cand is not self.unfilled:
                        print(f"Filling hole at {w}{d}{s} with {cand.name}")
                        self.state[w, d, s] = cand
                        improved = True
                        break
                else:
                    # try swapping this violation with every other filled slot
                    done = False
                    for w2 in range(W):
                        for d2 in range(D):
                            for s2 in range(S):
                                emp2 = self.state[w2, d2, s2]
                                if emp2 is self.unfilled or (w2,d2,s2)==(w,d,s):
                                    continue
                                if self.try_swap(w, d, s, w2, d2, s2, current_score):
                                    improved = done = True
                                    break
                            if done: break
                        if done: break
                    if improved:
                        break

        print("Finished repairs in", iters, "iterations." if improved else f"No further repairs after {iters}")
        # ensure numpy shape
        self.state = np.array(self.state)
        return self.state, history_epochs, history_score

    # swap method to reassign 2 employees to each other's shifts and check constraints
    # if improved, keep and return True, otherwise revert and return false
    def try_swap(self, w, d, s, w2, d2, s2, current_score):
        emp1 = self.state[w, d, s]
        emp2 = self.state[w2, d2, s2]
        # swap
        self.state[w, d, s], self.state[w2, d2, s2] = emp2, emp1
        # check absolute constraints on both
        for (ww, dd, ss, e) in ((w,d,s,emp2), (w2,d2,s2,emp1)):
            for c in e.getConstraints():
                if c.ctype == constraintType.ABSOLUTE and not c.isSatisfied(self.state, ww, dd, ss):
                    # undo
                    self.state[w, d, s], self.state[w2, d2, s2] = emp1, emp2
                    return False
        new_score = self.score(self.state)
        if new_score < current_score:
            print(f"Repair: swapped {emp1.name}@{w}{d}{s} with {emp2.name}@{w2}{d2}{s2} "
                  f"{current_score}→{new_score}")
            return True
        # undo
        self.state[w, d, s], self.state[w2, d2, s2] = emp1, emp2
        return False
