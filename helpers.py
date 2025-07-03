import numpy as np
from enum import Enum

HOURSPERSHIFT = 12

class weekdays(Enum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6

class constraintType(Enum):
    RELATIVE = 10
    ABSOLUTE = np.inf  # infinite penalty

class validStaffConstraint(Enum):
    HOURS_PER_PAY_PERIOD = 'Hours Per Pay Period'
    DAYSHIFTS_PER_WEEK = 'Day Shifts Per Week'
    NIGHTSHIFTS_PER_WEEK = 'Night Shifts Per Week'
    WEEKEND_ROTATION = 'Weekend Rotation'
    CONSECUTIVE_DAYS = 'Consecutive Days'
    CAN_WORK_MONDAY = 'Can Work Monday'
    CAN_WORK_TUESDAY = 'Can Work Tuesday'
    CAN_WORK_WEDNESDAY = 'Can Work Wednesday'
    CAN_WORK_THURSDAY = 'Can Work Thursday'
    CAN_WORK_FRIDAY = 'Can Work Friday'
    CAN_WORK_SATURDAY = 'Can Work Saturday'
    CAN_WORK_SUNDAY = 'Can Work Sunday'
    NO_DAY_AFTER_NIGHT = 'No Day After Night'
    MINIMUM_HOURS = 'Minimum Hours'
    ONE_PER_DAY = "One Shift Per Day"
    MIN_REST = "Minimum Rest"
    OVERLOADED = "Overloaded Week"

class validGlobalConstraint(Enum):
    D1_SHIFTS_FILLED = 'Dayshifts 1 Filled'
    D2_SHIFTS_FILLED = 'Dayshifts 2 Filled'
    NIGHT_SHIFTS_FILLED = 'Nightshifts Filled'

#contraint class defines constraints and contains methods for adding, removing, and checking constraint satisfaction in the current state
class Constraint:
    def __init__(self, name: str, val: float, ctype: constraintType):
        self.name = name
        self.val = val
        self.ctype = ctype

    def isSatisfied(self, schedule: np.ndarray, week: int, day: int, slot: int) -> bool:
        W, D, S = schedule.shape

        # Global: dayshift slot 0
        if self.name == validGlobalConstraint.D1_SHIFTS_FILLED.value:
            for w in range(W):
                for d in range(D):
                    e = schedule[w, d, 0]
                    if not e or getattr(e, 'name', None) == 'UNFILLED':
                        return False
            return True

        # Global: dayshift slot 1, skip Tue/Fri and biweekly weekend off
        if self.name == validGlobalConstraint.D2_SHIFTS_FILLED.value:
            for w in range(W):
                for d in range(D):
                    if d in (weekdays.Tuesday.value, weekdays.Friday.value):
                        continue
                    if d in (weekdays.Saturday.value, weekdays.Sunday.value) and (w % 2) == 1:
                        continue
                    e = schedule[w, d, 1]
                    if not e or getattr(e, 'name', None) == 'UNFILLED':
                        return False
            return True

        # Global: night shifts
        if self.name == validGlobalConstraint.NIGHT_SHIFTS_FILLED.value:
            for w in range(W):
                for d in range(D):
                    e = schedule[w, d, 2]
                    if not e or getattr(e, 'name', None) == 'UNFILLED':
                        return False
            return True

        # Skip empty/unfilled for staff rules
        emp = schedule[week, day, slot]
        if not emp or getattr(emp, 'name', None) == 'UNFILLED':
            return True

        # HOURS_PER_PAY_PERIOD
        if self.name == validStaffConstraint.HOURS_PER_PAY_PERIOD.value:
            if week % 2 == 0:
                return True  # only check at end of pay period

            start = week-1
            end = week+1
            total = 0
            for w in range(start, end):
                for d in range(D):
                    for s in range(S):
                        if schedule[w, d, s] is emp:
                            total += HOURSPERSHIFT
            return total <= self.val
        
        if self.name == validStaffConstraint.ONE_PER_DAY.value:
            cnt = sum(1 for s in range(S) if schedule[week, day, s] is emp)
            return cnt <= 1

        # DAYSHIFTS_PER_WEEK (slots 0 & 1)
        if self.name == validStaffConstraint.DAYSHIFTS_PER_WEEK.value:
            cnt = sum(
                1
                for d in range(D)
                for s in (0, 1)
                if schedule[week, d, s] is emp
            )
            return cnt <= self.val

        # NIGHTSHIFTS_PER_WEEK (slot 2)
        if self.name == validStaffConstraint.NIGHTSHIFTS_PER_WEEK.value:
            cnt = sum(
                1
                for d in range(D)
                if schedule[week, d, 2] is emp
            )
            return cnt <= self.val
        
        if self.name == validStaffConstraint.OVERLOADED.value:
            cnt = sum(
                1
                for d in range(D)
                if schedule[week, d, :] is emp
            )
            return cnt < self.val

        # CAN_WORK_X constraints
        day_map = {
            validStaffConstraint.CAN_WORK_MONDAY.value:    weekdays.Monday.value,
            validStaffConstraint.CAN_WORK_TUESDAY.value:   weekdays.Tuesday.value,
            validStaffConstraint.CAN_WORK_WEDNESDAY.value: weekdays.Wednesday.value,
            validStaffConstraint.CAN_WORK_THURSDAY.value:  weekdays.Thursday.value,
            validStaffConstraint.CAN_WORK_FRIDAY.value:    weekdays.Friday.value,
            validStaffConstraint.CAN_WORK_SATURDAY.value:  weekdays.Saturday.value,
            validStaffConstraint.CAN_WORK_SUNDAY.value:    weekdays.Sunday.value,
        }
        if self.name in day_map:
            if day == day_map[self.name] and not bool(self.val):
                return False
            return True

        # WEEKEND_ROTATION: allow up to 1 back-to-back weekend (i.e., max 2 in a row)
        if self.name == validStaffConstraint.WEEKEND_ROTATION.value:
            # Collect all weeks where employee worked a weekend shift
            worked_weekends = []
            for w in range(W):
                if any(
                    schedule[w, d, s] is emp
                    for d in (weekdays.Saturday.value, weekdays.Sunday.value)
                    for s in range(S)
                ):
                    worked_weekends.append(w)

            if not worked_weekends:
                return True  # No weekends worked, so valid

            max_run = curr_run = 1
            prev_week = worked_weekends[0]
            for w in worked_weekends[1:]:
                if w == prev_week + 1:
                    curr_run += 1
                else:
                    curr_run = 1
                max_run = max(max_run, curr_run)
                prev_week = w

            # Allow up to 2 consecutive weekends (1 back-to-back)
            return max_run <= 2


        # CONSECUTIVE_DAYS: no more than value contiguous days
        if self.name == validStaffConstraint.CONSECUTIVE_DAYS.value:
            worked = [
                any(schedule[week, d, s] is emp for s in range(S))
                for d in range(D)
            ]
            max_run = curr = 0
            for wkd in worked:
                if wkd:
                    curr += 1
                    max_run = max(max_run, curr)
                else:
                    curr = 0
            return max_run <= self.val

        # No day shifts for 2 days after working a night shift,
        # and no night shifts if the next day has a scheduled day shift
        if self.name == validStaffConstraint.NO_DAY_AFTER_NIGHT.value:
            W, D, S = schedule.shape

            if slot in (0, 1):  # day shift
                # Look back 1–2 days for prior night shifts
                for offset in (1, 2):
                    new_day = day - offset
                    week_delta, neighbour_day = divmod(new_day, D)
                    neighbour_week = (week + week_delta) % W
                    if schedule[neighbour_week, neighbour_day, 2] is emp:
                        return False

            elif slot == 2:  # night shift
                # Look ahead 1 day for next-day day shifts
                new_day = day + 1
                week_delta, neighbour_day = divmod(new_day, D)
                neighbour_week = (week + week_delta) % W
                if schedule[neighbour_week, neighbour_day, 0] is emp or schedule[neighbour_week, neighbour_day, 1] is emp:
                    return False

            return True

        # MINIMUM_HOURS
        if self.name == validStaffConstraint.MINIMUM_HOURS.value:
            if week % 2 == 0:
                return True  # Only check at end of pay period

            start = week - 1
            end = min(week + 2, W)  
            total = 0
            for w in range(start, end):
                for d in range(D):
                    for s in range(S):
                        if schedule[w, d, s] is emp:
                            total += HOURSPERSHIFT
            return total >= self.val
        
        # MIN_REST: at least self.val days between any two shifts
        if self.name == validStaffConstraint.MIN_REST.value:
            # helper to check if emp works at (w,d)
            def works(w, d):
                return any(schedule[w % W, d % D, s] is emp for s in range(S))

            # If they work the day before or after, that's consecutive and always allowed
            if works(week, day - 1) or works(week, day + 1):
                return True

            # enforce the minimum‐rest window
            for delta in range(1, int(self.val) + 1):
                if works(week, day - delta) or works(week, day + delta):
                    return False

            return True

        # Unknown constraint
        print(f"unhandled constraint {self.name}")
        return True

# class to represent employee with constraints to represent employee preferences
class Employee:
    def __init__(self, name: str, FTE: float):
        self.name = name
        self.FTE = FTE
        self.constraints: list[Constraint] = []
        self.totalShifts = 0
        self.setDefaultConstraints()

    def __str__(self):
        return self.name
    
    def __eq__(self, other):
        return isinstance(other, Employee) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def addConstraint(self, key: validStaffConstraint, val, ctype: constraintType):
        constraint = Constraint(key.value, val, ctype)
        self.constraints.append(constraint)

    def removeConstraint(self, key: validStaffConstraint):
        self.constraints = [c for c in self.constraints if c.name != key.value]

    def changeConstraint(self, key: validStaffConstraint, updated: Constraint):
        self.removeConstraint(key)
        self.constraints.append(updated)

    def getConstraints(self) -> list[Constraint]:
        return self.constraints

    def setDefaultConstraints(self):
        if self.name == 'UNFILLED':
            return

        self.addConstraint(validStaffConstraint.HOURS_PER_PAY_PERIOD, 80 * self.FTE, constraintType.ABSOLUTE)
        self.addConstraint(validStaffConstraint.DAYSHIFTS_PER_WEEK, 4, constraintType.RELATIVE)
        self.addConstraint(validStaffConstraint.OVERLOADED, 5, constraintType.ABSOLUTE)
        self.addConstraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK, 4, constraintType.RELATIVE)
        self.addConstraint(validStaffConstraint.WEEKEND_ROTATION, 1, constraintType.ABSOLUTE)
        self.addConstraint(validStaffConstraint.NO_DAY_AFTER_NIGHT, True, constraintType.ABSOLUTE)
        self.addConstraint(validStaffConstraint.CONSECUTIVE_DAYS, 3, constraintType.RELATIVE)
        self.addConstraint(validStaffConstraint.MINIMUM_HOURS, 80 * self.FTE * 0.8, constraintType.RELATIVE)
        self.addConstraint(validStaffConstraint.ONE_PER_DAY, True, constraintType.ABSOLUTE)
        self.addConstraint(validStaffConstraint.MIN_REST, 2, constraintType.RELATIVE)

        for day in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'):
            self.addConstraint(getattr(validStaffConstraint, f'CAN_WORK_{day.upper()}'), True, constraintType.RELATIVE)

        self.setActualConstraints()

    def setActualConstraints(self):
        match self.name:
            case "David":
                self.changeConstraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK,
                                    Constraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK.value, 0, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CAN_WORK_MONDAY,
                                    Constraint(validStaffConstraint.CAN_WORK_MONDAY.value, False, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CAN_WORK_TUESDAY,
                                    Constraint(validStaffConstraint.CAN_WORK_TUESDAY.value, False, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CAN_WORK_FRIDAY,
                                    Constraint(validStaffConstraint.CAN_WORK_FRIDAY.value, False, constraintType.ABSOLUTE))
            case "Kati":
                self.changeConstraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK,
                                    Constraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK.value, 0, constraintType.ABSOLUTE))
            case "Britt":
                self.changeConstraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK,
                                    Constraint(validStaffConstraint.NIGHTSHIFTS_PER_WEEK.value, 0, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CAN_WORK_WEDNESDAY,
                                    Constraint(validStaffConstraint.CAN_WORK_WEDNESDAY.value, False, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CONSECUTIVE_DAYS,
                                    Constraint(validStaffConstraint.CONSECUTIVE_DAYS.value, 5, constraintType.ABSOLUTE))
            case "Liz":
                self.changeConstraint(validStaffConstraint.DAYSHIFTS_PER_WEEK,
                                    Constraint(validStaffConstraint.DAYSHIFTS_PER_WEEK.value, 0, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CONSECUTIVE_DAYS, Constraint(validStaffConstraint.CONSECUTIVE_DAYS.value, 3, constraintType.ABSOLUTE))
            case "Ashley":
                self.changeConstraint(validStaffConstraint.DAYSHIFTS_PER_WEEK,
                                    Constraint(validStaffConstraint.DAYSHIFTS_PER_WEEK.value, 0, constraintType.ABSOLUTE))
                self.changeConstraint(validStaffConstraint.CONSECUTIVE_DAYS, Constraint(validStaffConstraint.CONSECUTIVE_DAYS.value, 3, constraintType.ABSOLUTE))
            case "Josh" | "Megan":
                pass
            case _:
                pass

class staffRoster(Enum):
    UNFILLED = Employee('UNFILLED', 0)
    David = Employee('David', 0.5)
    Josh = Employee('Josh', 1)
    Kati = Employee('Kati', 1)
    Britt = Employee('Britt', 1)
    Liz = Employee('Liz', 1)
    Megan = Employee('Megan', 1)
    Ashley = Employee('Ashley', 1)

# class contains methods to set and monitor global constraints, print the current state, and find/print/return current state constraint violations
class ScheduleBalancer:
    def __init__(self, state: np.ndarray, daypool: list[Employee],nightpool: list[Employee], floatpool: list[Employee], unfilled: list[Employee]):
        self.state = state
        self.daypool = daypool
        self.nightpool = nightpool
        self.floatpool = floatpool
        self.all_employees = daypool + nightpool + floatpool
        self.unfilled = unfilled
        self.constraints: list[Constraint] = []
        # Global constraints
        self.addConstraint(validGlobalConstraint.D1_SHIFTS_FILLED, True, constraintType.ABSOLUTE)
        self.addConstraint(validGlobalConstraint.D2_SHIFTS_FILLED, True, constraintType.ABSOLUTE)
        self.addConstraint(validGlobalConstraint.NIGHT_SHIFTS_FILLED, True, constraintType.ABSOLUTE)

    def __str__(self):
        try:
            state = np.array(self.state)
            if state.ndim != 3:
                return f"[Invalid state shape: {state.shape}]"
            string = ""
            for week in range(state.shape[0]):
                string += f"Week: {week}\n"
                for day in range(7):
                    d1 = state[week, day, 0]
                    d2 = state[week, day, 1]
                    n = state[week, day, 2]
                    string += f"Day {day}: {d1},{d2} | Night: {n}\n"
            return string
        except Exception as e:
            return f"[Error rendering schedule: {e}]"

    def addConstraint(self, which: validGlobalConstraint, val: float, ctype: constraintType):
        self.constraints.append(Constraint(which.value, val, ctype))

    #separate the relative constraint violations, this should only check if the schedule is valid (ie: no absolute violations)
    def isValidSchedule(self, schedule=None):
        
        sched = schedule if schedule is not None else self.state
        W,D,S = sched.shape
        globalAbsViolation = globalRelViolation = staffAbsViolation = staffRelViolation = 0
        violations = []
        for c in self.constraints:
            ok = c.isSatisfied(sched, None, None, None)
            if c.ctype == constraintType.ABSOLUTE and not ok:
                return False
        
        for w in range(W):
            for d in range(D):
                for s in range(S):
                    emp = sched[w,d,s]
                    if emp is None or emp.name=='UNFILLED':
                        continue
                    for c in emp.getConstraints():
                        ok = c.isSatisfied(sched, w, d, s)
                        if c.ctype == constraintType.ABSOLUTE and not ok:
                            return False

        return True

    def numViolations(self, schedule=None):
        
        sched = schedule if schedule is not None else self.state
        W,D,S = sched.shape
        globalAbsViolation = globalRelViolation = staffAbsViolation = staffRelViolation = 0
        violations = []
        for c in self.constraints:
            ok = c.isSatisfied(sched, None, None, None)
            if c.ctype == constraintType.ABSOLUTE and not ok:
                globalAbsViolation += 1
                violations.append(f"global absolute violation {c.name}")
            elif c.ctype == constraintType.RELATIVE and not ok:
                globalRelViolation += 1
                violations.append(f"global relative violation {c.name}")
        
        for w in range(W):
            for d in range(D):
                for s in range(S):
                    emp = sched[w,d,s]
                    if emp is None or emp.name=='UNFILLED':
                        continue
                    for c in emp.getConstraints():
                        ok = c.isSatisfied(sched, w, d, s)
                        if c.ctype == constraintType.ABSOLUTE and not ok:
                            staffAbsViolation +=1
                            violations.append(f"{emp} absolute violation {c.name} on {w}{d}{s}")
                        elif c.ctype == constraintType.RELATIVE and not ok:
                            staffRelViolation +=1
                            violations.append(f"{emp} relative violation {c.name} on {w}{d}{s}")

        return globalAbsViolation, globalRelViolation, staffAbsViolation, staffRelViolation, violations
    
    #separate the relative constraint violations, this should only check if the schedule is valid (ie: no absolute violations)
    def printViolations(self, schedule=None):
        globalAbsViolation, globalRelViolation, staffAbsViolation, staffRelViolation, violations = self.numViolations(schedule)
        
        for violation in violations:
            print(violation)
        
        print(f"Global Abs Violation: {globalAbsViolation}")
        print(f"Global Rel Violation: {globalRelViolation}")
        print(f"Staff Abs Violation: {staffAbsViolation}")
        print(f"Staff Rel Violation: {staffRelViolation}")