import numpy as np
import random

from Solver import Solver
from helpers import (
    weekdays,
    staffRoster,
    ScheduleBalancer,
    validStaffConstraint
)
import csv
import matplotlib.pyplot as pp
import pandas as pd
from openpyxl.utils import get_column_letter

PATHIN = "startingTemplate.csv"
PATHOUT = 'template.xlsx'
WEEKS = 4
SHIFTLENGTH = 12 #hours
NUM_SHIFTS = 3  # D1, D2, N
DAYS_PER_WEEK = 7

class Templater:
    def __init__(self):
        self.employees = self._create_employees()
        self.day_pool, self.night_pool, self.float_pool = self._build_pools(self.employees)
        self.unfilled = next(e for e in self.employees if e.name == "UNFILLED")
        self.david = next(e for e in self.employees if e.name == "David")

    def _create_employees(self):
        return [staff.value for staff in staffRoster]

    def _build_pools(self, employees):
        daypool, nightpool, floatpool = [], [], []

        for emp in employees:
            can_do_nights = True
            can_do_days = True

            # Check for day/night shift restrictions (0 shifts per week)
            for c in emp.getConstraints():
                if emp.name == "UNFILLED":
                    continue
                if c.name == validStaffConstraint.NIGHTSHIFTS_PER_WEEK.value and c.val == 0:
                    can_do_nights = False
                if c.name == validStaffConstraint.DAYSHIFTS_PER_WEEK.value and c.val == 0:
                    can_do_days = False

            if can_do_days and not can_do_nights:
                daypool.append(emp)
            elif can_do_nights and not can_do_days:
                nightpool.append(emp)
            else:
                if emp.name != "UNFILLED":
                    floatpool.append(emp)

        return daypool, nightpool, floatpool

    # fills weekends, even week days are David + Another, odd weeks are emp + UNFILLED
    def fillWeekends(self, schedule):
        weeks, days, slots = schedule.shape
        day_rotation_base = [e for e in (self.day_pool + self.float_pool) if e.name != "David" and e.name != "UNFILLED"]
        night_rotation_base = [e for e in (self.float_pool + self.night_pool) if e.name != "David" and e.name != "UNFILLED"]
        
        # extend pools
        day_rotation = day_rotation_base[:]  
        while len(day_rotation) < weeks * 2:
            day_rotation.extend(day_rotation_base[:])

        night_rotation = night_rotation_base[:]  
        while len(night_rotation) < weeks * 2:
            night_rotation.extend(night_rotation_base[:])

        if not day_rotation: # Fallback if base pool is truly empty
            print("Warning: Day rotation pool is critically empty for weekends. Using UNFILLED.")
            day_rotation = [self.unfilled] * (schedule.shape[0] * 2) 
        if not night_rotation: # Fallback if base pool is truly empty
            print("Warning: Night rotation pool is critically empty for weekends. Using UNFILLED.")
            night_rotation = [self.unfilled] * (schedule.shape[0] * 2)

        for w in range(weeks):
            for d in (weekdays.Saturday.value, weekdays.Sunday.value):
                # Sunday inherits from Saturday for consistency in weekend pair
                if d == weekdays.Sunday.value:
                    schedule[w,d,0] = schedule[w,d-1,0]
                    schedule[w,d,1] = schedule[w,d-1,1] 
                    schedule[w,d,2] = schedule[w,d-1,2]
                else: # Saturday
                    if night_rotation:
                        emp_n = night_rotation[0]
                        night_rotation.pop(0)
                        schedule[w,d,2] = emp_n
                        night_rotation.append(emp_n)
                    else:
                        print("night pool empty")
                        exit(1)
                        schedule[w,d,2] = self.unfilled

                    schedule[w,d,1] = self.unfilled # D2 is UNFILLED

                    if w % 2 == 0: # Even week: David + one other for day shifts
                        schedule[w,d,0] = self.david # David is D1
                        
                        if day_rotation:
                            other_emp_d2 = day_rotation[0]
                            day_rotation.pop(0)
                            schedule[w,d,1] = other_emp_d2 # Other person is D2
                            day_rotation.append(other_emp_d2)
                        else:
                            print("day pool empty")
                            exit(1)
                            schedule[w,d,1] = self.unfilled # Fallback if day pool empty

                    else: # Odd week: One other person + UNFILLED for day shifts
                        if day_rotation:
                            other_emp_d1 = day_rotation[0]
                            day_rotation.pop(0)
                            schedule[w,d,0] = other_emp_d1 # Other person is D1
                            day_rotation.append(other_emp_d1)
                        else:
                            print("day pool empty")
                            exit(2)
                            schedule[w,d,0] = self.unfilled # Fallback if day pool empty
                        
        return schedule

    #takes number of desired weeks, creates
    def makeTemplate(self, numWeeks: int, fill=False) -> np.ndarray:
        weeks, days, slots = numWeeks, 7, 3
        schedule = np.empty((weeks, days, slots), dtype=object)

        if fill:
            schedule = self.import_schedule_from_csv()
            return schedule

        for week in range(weeks):
            for day in range(days):
                #skip weekends, they are handled separately
                if day in [weekdays.Saturday.value, weekdays.Sunday.value]:
                    continue
                #unfill all weekdays
                for slot in range(3):
                    schedule[week,day,slot] = self.unfilled
                #every other week, assign david to d2 on wednesday
                if week % 2 == 0 and day in [weekdays.Wednesday.value]:
                     schedule[week,day,1] = self.david

        #fill the weekends
        schedule = self.fillWeekends(schedule)

        return schedule

    #output a CSV of template
    #CSV reader and writer not fully implemented
    # def export_schedule_to_csv(self, schedule: np.ndarray):
    #     """
    #     Writes out a CSV with columns: week,day,slot,employee_name
    #     schedule.shape == (weeks, 7, 3)
    #     """
    #     weeks, days, slots = schedule.shape
    #     with open(PATHOUT, 'w', newline='') as csvfile:
    #         writer = csv.writer(csvfile)
    #         writer.writerow(['week','day','slot','employee'])
    #         for w in range(weeks):
    #             for d in range(days):
    #                 for s in range(slots):
    #                     emp = schedule[w, d, s]
    #                     name = emp.name if emp is not None else ''
    #                     writer.writerow([w, d, s, name])

    def export_schedule_to_xlsx(self, schedule: np.ndarray):
        W, D, S = schedule.shape
        SHIFT_HOURS = 12
        day_names = ['Mo','Tu','We','Th','Fr','Sa','Su']

        # 1) Build D1, D2, N tables
        tables = {}
        for idx, label in enumerate(('D1','D2','N')):
            data = []
            for w in range(W):
                row = []
                for d in range(7):
                    row.append(schedule[w,d,idx].name if schedule[w,d,idx].name!='UNFILLED' else '')
                data.append(row)

            while len(data) < W:
                data.append(['']*7)

            tables[label] = pd.DataFrame(data, columns=day_names).assign(Week=lambda df: df.index + 1).set_index('Week')

        # 2) Build the summary DataFrame
        all_emps = {e for e in schedule.flatten() if e.name!='UNFILLED'}
        summary_rows = []
        for emp in sorted(all_emps, key=lambda e: e.name):
            total_hours = day_shifts = night_shifts = weekday_days = weekend_days = 0
            for w in range(W):
                for d in range(7):
                    worked = False
                    for s in range(3):
                        if schedule[w,d,s] is emp:
                            worked = True
                            total_hours += SHIFT_HOURS
                            if s in (0,1):
                                day_shifts += 1
                            else:
                                night_shifts += 1
                    if worked:
                        if d in (weekdays.Saturday.value, weekdays.Sunday.value):
                            weekend_days += 1
                        else:
                            weekday_days += 1
            summary_rows.append([
                emp.name, total_hours, day_shifts, night_shifts, weekday_days, weekend_days
            ])
        summary_df = pd.DataFrame(
            summary_rows,
            columns=[
                'Employee',
                'Total Hours',
                'Day Shifts',
                'Night Shifts',
                'Weekdays Worked',
                'Weekend Days Worked',
            ]
        )

        # 3) Build per-employee sheets
        personal_dfs = {}
        for emp in sorted(all_emps, key=lambda e: e.name):
            rows = []
            for w in range(W):
                week_hours = 0
                week_row = []
                for d in range(7):
                    slot = ''
                    for s,label in [(0,'D1'),(1,'D2'),(2,'N')]:
                        if schedule[w,d,s] is emp:
                            slot = label
                            week_hours += SHIFT_HOURS
                            break
                    week_row.append(slot)
                rows.append([w+1] + week_row + [week_hours])
            personal_dfs[emp.name] = pd.DataFrame(
                rows,
                columns=['Week'] + day_names + ['Hours']
            )

        # 4) Write everything to Excel
        with pd.ExcelWriter(PATHOUT, engine='openpyxl') as writer:
            ws = None

            # 4a) Master sheet: three tables stacked
            shift_labels = [('D1', 'Day 1'), ('D2', 'Day 2'), ('N', 'Night')]

            
            current_row_offset = 0
            for i, (key, label) in enumerate(shift_labels):
                # Calculate the starting row for each table.
                # Add 2 for initial spacing, then (W+5) for each table block
                # (W rows + header + index + spacing)
                start_row = current_row_offset + 2
                df = tables[key]

                # Write the DataFrame to the 'Master' sheet
                df.to_excel(
                    writer,
                    sheet_name='Master',
                    startrow=start_row,
                    startcol=0,
                    index=True,  # Write the 'Week' index as a column
                    header=True  # Write the column headers
                )

                # Get the worksheet object after the first write to avoid errors
                if ws is None:
                    ws = writer.book['Master']

                # Add a descriptive heading above each shift table
                # This heading should be merged across columns
                ws.cell(row=start_row, column=1).value = f"{label} Shifts"
                ws.merge_cells(
                    start_row=start_row,
                    start_column=1,
                    end_row=start_row,
                    end_column=1 + len(day_names) + 1  # 1 for 'Week' column, 1 for extra cell for aesthetics
                )

                # Adjust column headers explicitly if needed, but pd.to_excel usually handles this.
                # The user's original code sets them again; ensure no duplication or overwrite issues.
                # The 'Week' column header is handled by `index=True` in to_excel.
                # 'day_names' are handled by `header=True`.

                # Update the row offset for the next table
                current_row_offset = start_row + len(df) + 3 # Add rows of df + header + index + 2 for spacing

            # 4b) Summary heading + table below the last N table
            summary_start_row = current_row_offset + 2 # Add some space after the last shift table

            # Merge "Summary" across columns A-F (or as many columns as the summary_df has)
            # The summary_df has 6 columns
            ws.merge_cells(
                start_row=summary_start_row,
                start_column=1,
                end_row=summary_start_row,
                end_column=len(summary_df.columns)
            )
            ws.cell(row=summary_start_row, column=1).value = "Summary"

            # Write the summary DataFrame
            summary_df.to_excel(
                writer,
                sheet_name='Master',
                startrow=summary_start_row + 1,  # Start after the 'Summary' heading
                startcol=0,
                index=False, # Do not write DataFrame index
                header=True  # Write column headers
            )

            # 4c) Write each personal sheet
            for name, df in personal_dfs.items():
                # Ensure sheet name is <= 31 characters, which is an Excel limit
                df.to_excel(writer, sheet_name=name[:31], index=False)

            # 5) Auto-size all columns on the 'Master' sheet for better readability
            if ws: # Ensure ws exists before trying to iterate
                for column_cells in ws.columns:
                    max_length = 0
                    column = column_cells[0].column # Get the column number
                    for cell in column_cells:
                        try:
                            # Calculate length based on cell value, handling None
                            if cell.value is not None:
                                max_length = max(max_length, len(str(cell.value)))
                        except Exception:
                            pass # Ignore errors for cells that might not have a simple string representation
                    adjusted_width = (max_length + 2) # Add a small buffer
                    ws.column_dimensions[get_column_letter(column)].width = adjusted_width


    def import_schedule_from_csv(self) -> np.ndarray:
        
        df = pd.read_csv(PATHIN, header=None)

        daypool = [e for e in self.day_pool if e.name != "David"]

        employeeMap = {
            0: self.unfilled,
            1: self.night_pool[0],
            2: self.night_pool[1],
            3: self.float_pool[0],
            4: self.float_pool[1],
            5: daypool[0],
            6: daypool[1],
            7: self.david
        }

        num_weeks = df.shape[0] // NUM_SHIFTS
        num_days = df.shape[1]  
        schedule = []

        for week in range(num_weeks):
            week_schedule = []
            start_row = week * NUM_SHIFTS
            
            for day in range(DAYS_PER_WEEK):
                day_shift = []
                
                for shift in range(NUM_SHIFTS):
                    value = df.iloc[start_row + shift, day]
                    if pd.isna(value):
                        day_shift.append(self.unfilled)
                    else:
                        day_shift.append(employeeMap.get(int(value), None))
                week_schedule.append(day_shift)
            
            schedule.append(week_schedule)
        schedule = np.array(schedule)

        return schedule

#graph of score over time
def createFigure(epochs, scores):
    figure, axis = pp.subplots()
    axis.plot(epochs, scores)
    pp.xlabel("Epochs")
    pp.ylabel("Score")
    pp.show()

#feasibility check to quick fail an unsolvable problem
def isFeasible(employees, total_weeks=WEEKS):
    num_even_weeks = total_weeks // 2
    num_odd_weeks = total_weeks - num_even_weeks
    total_weekday_shifts = num_even_weeks * (3 * 5) + num_odd_weeks * (2 * 5)

    total_weekend_shifts = total_weeks * (2 * 2) 

    total_required_shifts = total_weekday_shifts + total_weekend_shifts
    required_hours = total_required_shifts * SHIFTLENGTH

    total_available_hours = sum(
        next(c.val for c in emp.getConstraints() if c.name == validStaffConstraint.HOURS_PER_PAY_PERIOD.value) * (total_weeks // 2)
        for emp in employees if emp.name != "UNFILLED"
    )

    print(f"Total required shifts over {total_weeks} weeks: {total_required_shifts} (Total Hours: {required_hours})")
    print(f"Total available hours from staff: {total_available_hours}")

    if total_available_hours < required_hours:
        print("⚠️ WARNING: Not enough staff-hours to cover all shifts.")
        return False
    else:
        print("✅ Staff-hour capacity seems sufficient.")
        return True
# Main execution block
if __name__ == "__main__":
    # ---------------------------------- INITIALIZATIONS -------------------------------------------
    templater = Templater()
    employees = templater.employees
    daypool = templater.day_pool
    nightpool = templater.night_pool
    floatpool = templater.float_pool
    unfilled = templater.unfilled

    initial_schedule = templater.makeTemplate(WEEKS, fill=True)
    
    # Initialize ScheduleBalancer with the initial schedule
    schedule_balancer = ScheduleBalancer(initial_schedule, daypool, nightpool, floatpool, unfilled) 

    # ---------------------------------- SOLVING FUNCTIONS -------------------------------------------
    agent = Solver(schedule_balancer, daypool, nightpool, floatpool, unfilled)

    if not isFeasible(employees):
        exit(0)

    schedule, final_score, epochs, scores = agent.greedySearch()
    
    # ---------------------------------- EVAL AND PRINTING FUNCTIONS -------------------------------------------

    print("\n--- Final Best Solution ---")

    #schedule balancer contains the print functions
    schedule_balancer.state = schedule
    print(schedule_balancer)
    schedule_balancer.printViolations()

    #separate abs and rel violation counts from isValidSchedule
    if not schedule_balancer.isValidSchedule():
        print("Invalid Schedule Created")
  
    print(f"Final Score: {final_score}")

    #print, graph, export to csv  
    templater.export_schedule_to_xlsx(schedule)

    #hours count per employee per week
    weeks, days, slots = schedule.shape
    for emp in employees:
        total_hours = 0
        for week in range(weeks):
            for day in range(7):
                for slot in range(3):
                    if schedule[week, day, slot] is emp:
                        total_hours += SHIFTLENGTH
        print(f"{emp.name}: {total_hours} hrs worked total")

    for emp in employees:
        print(f"{emp.name}:")
        for pay_start in range(0, weeks, 2):
            total_hours = 0
            for w in range(pay_start, min(pay_start+2, weeks)):
                for d in range(7):
                    for s in range(3):
                        if schedule[w, d, s] is emp:
                            total_hours += SHIFTLENGTH
            print(f"  Weeks {pay_start}-{pay_start+1}: {total_hours} hrs")
    
    #print figure
    createFigure(epochs, scores)
