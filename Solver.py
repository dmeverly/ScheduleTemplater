import numpy as np
import random
from helpers import (
    weekdays,
    ScheduleBalancer,
    validStaffConstraint,
    constraintType,
    Employee,
)
import math

ABS_PENALTY = 10000
EPOCH_LIMIT = 1000
SHIFTLENGTH = 12  # hours
TEMPERATURE = 1000
COOLING = 0.9995
PATIENCE = 300

# agent tasked with solving constraint satisfaction problem
# uses greedy search with simulated annealing, followed by local repair and local search
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

        self.temperature = TEMPERATURE
        self.cooling_rate = COOLING

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
        best_combined = float('inf')

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
            softCost = self._soft_cost_eval(schedule, w, d, s, emp)
            combined = delta + softCost  
            
            if combined < best_combined:
                best_candidate = emp
                best_combined   = combined

            elif combined == best_combined:
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
        # adjacency bonus - bias toward working stretches of days
        if (d > 0 and emp in schedule[w, d-1, :]) or (d < schedule.shape[1]-1 and emp in schedule[w, d+1, :]):
            max_consec = next(
                (c.val for c in emp.getConstraints()
                if c.name == validStaffConstraint.CONSECUTIVE_DAYS.value),
                None
            )

            if max_consec is not None:
                prev_run = 0
                dd = d-1
                while dd >= 0 and any(schedule[w, dd, s] is emp for s in range(3)):
                    prev_run += 1
                    dd -= 1

                next_run = 0
                dd = d+1
                D = schedule.shape[1]
                while dd < D and any(schedule[w, dd, s] is emp for s in range(3)):
                    next_run += 1
                    dd += 1

                total_run = prev_run + 1 + next_run

                if total_run <= max_consec:
                    cost -= 3000  # bonus = -3000 for runs

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

        #fill all the unfilled shifts until no more moves can be made
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
        
        W,D,S = self.state.shape
        #shuffle choices, find violations, try 2-way swap 
        violations = []
        for w in range(W):
            for d in range(D):
                if d in (weekdays.Saturday.value, weekdays.Sunday.value):
                    continue
                for s in range(S):
                    emp = self.state[w,d,s]
                    if emp is self.unfilled: continue
                    for c in emp.getConstraints():
                        if not c.isSatisfied(self.state, w, d, s):
                            violations.append((w,d,s))
                            break
        if len(violations) == 1:
            w,d,s = violations[0]
            trial_state, trial_hours = self.state.copy(), self.hours_used.copy()
            cand = self._select_employee_for_slot(trial_state, w, d, s, trial_hours)
            if cand is not self.unfilled:
                trial_state[w,d,s] = cand
                return trial_state, trial_hours
        if len(violations) <= 0:
            return None, None

        for i in range(len(violations)):
            # pick two random distinct violating slots
            (w1,d1,s1), (w2,d2,s2) = random.sample(violations, 2)
            trial_state = self.state.copy()
            trial_hours = self.hours_used.copy()
            emp1, emp2 = trial_state[w1,d1,s1], trial_state[w2,d2,s2]
            # swap them
            trial_state[w1,d1,s1], trial_state[w2,d2,s2] = emp2, emp1
            currGABS, _, currSABS, _, _ = self.balancer.numViolations(self.state)
            trialGABS, _, trialSABS, _, _ = self.balancer.numViolations(trial_state)
            if trialGABS > currGABS or trialSABS > currSABS:
                continue
            else:
                return trial_state, trial_hours
        return None, None

    # score constraint violations and unfilled shifts +1 for each relative violation and +50 for each unfilled shift, + ABS_PENALTY for absolute violations
    def score(self, schedule):
        g_abs, g_rel, s_abs, s_rel, _ = self.balancer.numViolations(schedule=schedule)
        W, _, _ = schedule.shape
        for w in range(W):
            for d in range(7):
                downstaff = d in (weekdays.Saturday.value, weekdays.Sunday.value,
                                  weekdays.Tuesday.value, weekdays.Friday.value)
                for s in range(3):
                    if downstaff and s == 1:
                        continue
                    if schedule[w, d, s].name == "UNFILLED":
                        g_abs += 50
        return (g_abs + s_abs) * ABS_PENALTY + g_rel + s_rel

    # SA decision to accept proposal, always accept better scoring states, randomly accept worse states
    def acceptOffer(self,new_score):
        if new_score < self.current_score:
            return 1.0
        elif self.temperature <= 0:
            return 0.0
        else:
            return math.exp((self.current_score-new_score)/self.temperature)

    def cool(self, acceptRate):
        coolingFactor = 1.0-(acceptRate-0.5)/2
        coolingFactor = max(0.9, min(1.1,coolingFactor))
        self.temperature *= self.cooling_rate
    
    # agent driver, fills initial schedule by greedy best search on most constrained variables
    # after schedule is full, searches to minimize cost by filling vacant shifts and looking for valid swaps
    # local repair for constraint violations
    # searches for underworked employees and attempts to find slot to place them in
    # final sweep to check for violations
    # every step checks pre- and post- score, if worse, revert back to previous state before proceeding
    def stateHandler(self):
        def snapshot():
            return (self.state.copy(),
                    self.current_score,
                    {w: h.copy() for w, h in self.hours_used.items()})

        def restore(snap):
            st, sc, hrs = snap
            self.state = st.copy()
            self.current_score = sc
            self.hours_used = {w: h.copy() for w, h in hrs.items()}
            self.balancer.state = self.state

        history_epochs, history_scores = [], []

        # 1) Greedy phase
        print(self.balancer)
        print(f"Starting Score: {self.current_score}")
        print("Starting greedy initialization…")
        greedy_snap = snapshot()
        greedy_state, greedy_score, history_epochs, history_scores = self.greedySearch()
        # after greedySearch, self.state/self.current_score are updated
        print("-----------------Greedy Phase Complete--------------")
        print(f"Greedy best state\n{self.balancer}")
        print(f"Score: {self.current_score}")

        # 2) Repair phase
        print("Starting post-Greedy repair…")
        repair_snap = snapshot()
        self.state, history_epochs, history_scores, _ = self.repair_schedule(history_epochs, history_scores)
        self.current_score = self.score(self.state)
        print(f"After Repair state\n{self.balancer}")
        print(f"Score: {self.current_score}")
        # Roll back if worse than greedy
        if self.current_score > greedy_score:
            print("Repair worsened relative cost—rolling back to greedy solution")
            restore(greedy_snap)
        repair_snap = snapshot()   # re-snapshot after possible rollback
        print("-----------------Repair Phase Complete--------------")

        # 3) Final-fill phase
        print("Filling Minimums…")
        fill_snap = snapshot()
        self.state, history_epochs, history_scores = self.finalFillMinimums(history_epochs, history_scores)
        self.current_score = self.score(self.state)
        print(f"After Filling state\n{self.balancer}")
        print(f"Score: {self.current_score}")
        # Roll back if worse than post-repair
        if self.current_score > repair_snap[1]:
            print("Filling worsened relative cost—rolling back to repair solution")
            restore(repair_snap)
        fill_snap = snapshot()
        print("-----------------Fill Phase Complete--------------")

        # 4) Final sweep
        print("Final Sweep…")
        sweep_snap = snapshot()
        self.state, history_epochs, history_scores = self.finalPass(history_epochs, history_scores)
        self.current_score = self.score(self.state)
        print(f"After Sweep state\n{self.balancer}")
        print(f"Score: {self.current_score}")
        # Roll back if worse than final-fill
        if self.current_score > fill_snap[1]:
            print("Sweep worsened relative cost—rolling back to fill solution")
            restore(fill_snap)

        print("-----------------Template Complete--------------")
        print(f"Final Score: {self.current_score}")
        return self.state, self.current_score, history_epochs, history_scores


    # greedy search with simulated annealing
    def greedySearch(self):     
        best_state = self.state.copy()
        best_score = self.current_score
        history_epochs, history_scores = [], []
        epoch = patience = acceptCounter = 0

        while epoch < EPOCH_LIMIT:
            # restart to best state if no change has been made for a while - defined by patience
            if patience > PATIENCE:
                print("Impatient Restart")
                self.state, self.current_score, self.hours_used = best_state, best_score, best_hours
                self.lastRejected = None
                self.temperature = TEMPERATURE
            epoch += 1
            if epoch % 100 == 0:
                print(f"Epoch {epoch}, current score: {self.current_score}, best score: {best_score}, heat: {self.temperature:.2f}")

            # propose move into slot and decide whether to accept
            new_state, h_map = self.propose_move()
            if new_state is None:
                break
            new_score = self.score(new_state)
            prob = self.acceptOffer(new_score)

            if random.random() < prob:
                self.state, self.hours_used, self.current_score = new_state, h_map, new_score
                self.lastRejected = None
                acceptCounter += 1
                patience = 0
            else:
                patience += 1
 
            if self.current_score < best_score:
                best_state, best_score = self.state.copy(), self.current_score
                best_hours = self.hours_used
            
            acceptRate = acceptCounter/epoch
            self.cool(acceptRate)

            history_epochs.append(epoch)
            history_scores.append(self.current_score)        
        self.state, self.current_score, self.hours_used = best_state, best_score, best_hours
        self.balancer.state = self.state
        greedy_state, greedy_score = self.state.copy(), self.current_score     
        return greedy_state, greedy_score, history_epochs, history_scores

    def find_violations(self):
            vio = []
            W, D, S = self.state.shape
            for w in range(W):
                for d in range(D):
                    if d in (weekdays.Saturday.value, weekdays.Sunday.value):
                        continue
                    for s in range(S):
                        emp = self.state[w, d, s]
                        if emp is self.unfilled:
                            continue
                        for c in emp.getConstraints():
                            if not c.isSatisfied(self.state, w, d, s):
                                if c.name == validStaffConstraint.MINIMUM_HOURS.value:
                                    continue
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
    
    # find violations in completed schedule and the best employee to fill them
    def repair_schedule(self, history_epochs, history_score):
        iters = 0
        improved = True
        W, D, S = self.state.shape

        while improved:
            iters += 1
            history_epochs.append(len(history_epochs)+1)
            history_score.append(self.current_score)
            improved = False
            current_score = self.score(self.state)
            violations = self.find_violations()

            # one entry per slot
            seen = set()
            slot_vio = []
            for emp, _, w, d, s in violations:
                if (w, d, s) not in seen:
                    seen.add((w, d, s))
                    slot_vio.append((emp, w, d, s))

            for emp, w, d, s in slot_vio:
                if d in (weekdays.Saturday.value, weekdays.Sunday.value):
                    continue
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
                            if d2 in (weekdays.Saturday.value, weekdays.Sunday.value):
                                continue
                            for s2 in range(S):
                                emp2 = self.state[w2, d2, s2]
                                if emp2 is self.unfilled or (w2,d2,s2)==(w,d,s):
                                    continue
                                if (any(self.state[w2,d2,:]) is emp) or (any(self.state[w,d,:]) is emp2):
                                    continue
                                if self.try_swap(w, d, s, w2, d2, s2, current_score):
                                    improved = done = True
                                    break
                            if done: break
                        if done: break
                    if improved:
                        break

        print("Finished repairs in", iters, "iterations." if improved else f"No further repairs after {iters} epochs")
        # ensure numpy shape
        self.state = np.array(self.state)
        return self.state, history_epochs, history_score, slot_vio

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
                    self.state[w, d, s], self.state[w2, d2, s2] = emp1, emp2
                    return False
        new_score = self.score(self.state)
        if new_score < current_score:
            print(f"Repair: swapped {emp1.name}@{w}{d}{s} with {emp2.name}@{w2}{d2}{s2} "
                  f"{current_score}→{new_score}")
            return True
        self.state[w, d, s], self.state[w2, d2, s2] = emp1, emp2
        return False
    
    def finalPass(self, history_epochs, history_scores):
        self.balancer.state = self.state
        _, _, staff_abs, _ , _= self.balancer.numViolations(schedule=self.state)

        # keep looping on *only* absolute violations
        while staff_abs > 0:
            history_epochs.append(len(history_epochs)+1)
            history_scores.append(self.score(self.state))
            print(f"Extra abs‐fix pass: {staff_abs} absolute violations remain")
            W, D, S = self.state.shape

            # find the first absolute violation slot
            found = False
            for w in range(W):
                if found: break
                for d in range(D):
                    if found: break
                    for s in range(S):
                        emp = self.state[w,d,s]
                        if emp is self.unfilled: 
                            slot_emp = self.unfilled
                        else:
                            abs_bads = [c for c in emp.getConstraints()
                                        if c.ctype == constraintType.ABSOLUTE
                                        and not c.isSatisfied(self.state, w, d, s)]
                            if not abs_bads:
                                continue
                            slot_emp = emp

                        candidate = self._select_employee_for_slot(self.state, w, d, s, self.hours_used)
                        if candidate is not self.unfilled and candidate is not slot_emp:
                            print(f"  fixing ABS slot {w}{d}{s}: {slot_emp.name} → {candidate.name}")
                            if slot_emp is not self.unfilled:
                                self.hours_used[w][slot_emp] -= SHIFTLENGTH
                            self.state[w,d,s] = candidate
                            self.hours_used[w][candidate] += SHIFTLENGTH
                            found = True
                            break
            if not found:
                # nothing fillable — try pair‐wise swap:
                # look for two slots whose swap removes an absolute
                for w1 in range(W):
                    for d1 in range(D):
                        for s1 in range(S):
                            e1 = self.state[w1,d1,s1]
                            if e1 is self.unfilled:
                                continue
                            if all(c.isSatisfied(self.state,w1,d1,s1) for c in e1.getConstraints() if c.ctype==constraintType.ABSOLUTE):
                                continue

                            for w2 in range(W):
                                for d2 in range(D):
                                    for s2 in range(S):
                                        e2 = self.state[w2,d2,s2]
                                        if e2 is self.unfilled:
                                            continue
                                        self.state[w1,d1,s1], self.state[w2,d2,s2] = e2, e1
                                        ok1 = all(c.isSatisfied(self.state,w1,d1,s1)
                                                for c in e2.getConstraints() if c.ctype==constraintType.ABSOLUTE)
                                        ok2 = all(c.isSatisfied(self.state,w2,d2,s2)
                                                for c in e1.getConstraints() if c.ctype==constraintType.ABSOLUTE)
                                        if ok1 and ok2:
                                            print(f"  swap ABS fix: ({w1}{d1}{s1}){e1.name}↔({w2}{d2}{s2}){e2.name}")
                                            found = True
                                            break
                                        # undo
                                        self.state[w1,d1,s1], self.state[w2,d2,s2] = e1, e2
                                    if found: break
                                if found: break
                            if found: break
                        if found: break
                    if found: break

            if not found:
                # if we couldn’t fix any slot, bail out to avoid infinite loop
                print("Could not repair an absolute violation — giving up.")
                break

            # re‐count remaining absolute violations
            _ , _, staff_abs, _, _ = self.balancer.numViolations()
        return self.state, history_epochs, history_scores

    def finalFillMinimums(self, history_epochs, history_scores):
        W, D, S = self.state.shape
        SH = SHIFTLENGTH

        def collect_underworked():
            uw = {}
            for emp in self.allPool:
                if emp is self.unfilled:
                    continue
                min_h = next((c.val for c in emp.getConstraints()
                            if c.name == validStaffConstraint.MINIMUM_HOURS.value), None)
                if min_h is None:
                    continue
                for pp_start in range(0, W, 2):
                    used = sum(
                        SH for w in range(pp_start, min(pp_start+2, W))
                        for d in range(D)
                        for s in range(S)
                        if self.state[w,d,s] is emp
                    )
                    missing = min_h - used
                    if missing > 0:
                        shifts_needed = (missing + SH - 1) // SH
                        uw.setdefault(emp, []).append((pp_start, shifts_needed))
            return uw

        def all_holes():
            return [
                (w,d,s)
                for w in range(W)
                for d in range(D)
                for s in range(S)
                if self.state[w,d,s] is self.unfilled
            ]

        def is_feasible(emp, w, d, s):
            if self.state[w,d,s] is not self.unfilled:
                return False
            self.state[w,d,s] = emp
            for c in emp.getConstraints():
                if c.ctype == constraintType.ABSOLUTE and not c.isSatisfied(self.state, w, d, s):
                    self.state[w,d,s] = self.unfilled
                    return False
            for gc in self.balancer.constraints:
                if gc.ctype == constraintType.ABSOLUTE and not gc.isSatisfied(self.state, None, None, None):
                    self.state[w,d,s] = self.unfilled
                    return False
            self.state[w,d,s] = self.unfilled
            return True

        def hours_in_pp(emp, pp_start):
            return sum(
                SH for w in range(pp_start, min(pp_start+2, W))
                for d in range(D)
                for s in range(S)
                if self.state[w,d,s] is emp
            )

        def apply_plan(plan):
            for emp, (w,d,s) in plan:
                self.state[w,d,s] = emp
                self.hours_used[w][emp] += SH

        def revert_plan(plan):
            for emp, (w,d,s) in plan:
                self.state[w,d,s] = self.unfilled
                self.hours_used[w][emp] -= SH

        while True:
            history_epochs.append(len(history_epochs)+1)
            history_scores.append(self.score(self.state))
            underworked = collect_underworked()
            if not underworked:
                break

            holes = all_holes()
            base_score = self.score(self.state)
            best_delta = float('inf')
            best_plan = None

            for emp, needs in underworked.items():
                for pp_start, shifts_needed in needs:
                    before_hours = hours_in_pp(emp, pp_start)
                    for hole in holes:
                        w, d, s = hole
                        if not is_feasible(emp, w, d, s):
                            continue
                        if not (pp_start <= w < pp_start+2):
                            continue  

                        plan = [(emp, hole)]
                        apply_plan(plan)
                        after_hours = hours_in_pp(emp, pp_start)
                        delta = self.score(self.state) - base_score

                        min_h = next((c.val for c in emp.getConstraints()
                                    if c.name == validStaffConstraint.MINIMUM_HOURS.value), None)
                        max_h = next((c.val for c in emp.getConstraints()
                                    if c.name == validStaffConstraint.HOURS_PER_PAY_PERIOD.value), None)
                        if min_h is not None:
                            if (before_hours < after_hours < min_h) and after_hours <= max_h:
                                delta -= 100  # reward partial progress
                            elif (before_hours < min_h <= after_hours) and after_hours <= max_h:
                                delta -= 500  # reward full fix

                        revert_plan(plan)
                        if delta < best_delta:
                            best_delta, best_plan = delta, plan

            if best_plan is None or best_delta > 0:
                break

            apply_plan(best_plan)
        return self.state, history_epochs, history_scores
