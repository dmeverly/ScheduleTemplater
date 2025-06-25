## Schedule Template Creation Using Greedy Search with Simulated Annealing

**Author**: David Everly  
**Language**: Python  
**License**: None  

---

## Problem Statement  
The project sponsor described issues with the existing scheduling workflow, which involved manually creating a schedule template and mapping it onto an annual calendar. Conflicting employee and business constraints resulted in excessive meetings and constant revisions. I was asked to automate both the creation of the template and its mapping to the calendar. 
  
# Description  
This program automates the template creation process by accepting a rough draft of a schedule and refining it using predefined global and employee-specific constraints. The system explores the state space using greedy search combined with simulated annealing until no significant improvements are observed. This is followed by local repair and local search phases to resolve any remaining constraint violations. The final template is exported as template.xlsx.

# Theoretical Approach
Scheduling is a classic constraint satisfaction problem. Many algorithms can be applied; however, given the size of the state space, exhaustive search (DFS, BFS) is impractical. Even when weekends are hardcoded, assigning 3 shifts per weekday for 6 weeks results in a state space of: 7<sup>90</sup>!  

Greedy search offers a faster alternative by selecting the best local option at each step. However, it risks getting stuck in local minima. Simulated Annealing addresses this by occasionally accepting worse states to escape these local optima. My approach combines both methods, followed by local search and repair, to thoroughly analyze and satisfy constraints.

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Configuration](#configuration)
- [Examples](#examples)
- [Results and Conclusion](#results-and-conclusion)
- [Future Work and Extension](#future-work-and-extension)
- [References](#references)
- [Contributing](#contributing)

# Installation
Dependencies:   
numpy  
pandas  
matplotlib  
openpyxl  

Install using:  
```bash
pip install -r requirements.txt  
```  

# Usage
Program is intended to be run using Unix-like terminal such as Linux, macOS Terminal (untested), or MINGW64 (Git Bash) on Windows.  

Run the script with: 
```bash 
python templater.py 
```  
Or use the provided shell script:    
```bash
./run  
```

# Features  
- Multi-week template generation  
- Custom employee constraints  
- Greedy intialization with annealing  
- Visualization of performance over time  
- Template in .xlsx format  

# Configuration  
- templater.py is the main script which begins initilization and flow orchestration.  
- Employee and constraint definitions are located in helpers.py.  These can be edited, including the addition of new constraints.  If new constraints are added, logic for constraint satisfaction needs to also be added.
- solver.py contains agent search and repair methods. Those wishing to solve using another model can extend solver.py with methods suited for other algorithms.  

# Examples  
Due to the stochastic nature of greedy search and simulated annealing, output will vary between runs. The algorithm continues refining the solution until it reaches a near-optimal state. Below is the progression from a single run:  

Initial state -> 280,004  
Greedy state  -> 70,009  
Repair state  -> 10,005  
Fill state    -> 10,000  
Final Sweep   -> 0  

<details>
<summary>Expand Command Line Output</summary>

```text
$ ./run
Total required shifts over 6 weeks: 99 (Total Hours: 1188)
Total available hours from staff: 1560.0
✅ Staff-hour capacity seems sufficient.
Week: 0
Day 0: Josh,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Kati,UNFILLED | Night: Liz
Day 3: Josh,Britt | Night: Ashley
Day 4: Josh,UNFILLED | Night: Ashley
Day 5: David,Kati | Night: Liz
Day 6: David,Kati | Night: Liz
Week: 1
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Josh
Day 2: David,Megan | Night: Ashley
Day 3: Kati,Britt | Night: Liz
Day 4: Kati,UNFILLED | Night: Liz
Day 5: Megan,UNFILLED | Night: Ashley
Day 6: Megan,UNFILLED | Night: Ashley
Week: 2
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Josh,UNFILLED | Night: Liz
Day 3: Megan,Britt | Night: Ashley
Day 4: Megan,UNFILLED | Night: Ashley
Day 5: David,Josh | Night: Liz
Day 6: David,Josh | Night: Liz
Week: 3
Day 0: Josh,Megan | Night: Liz
Day 1: Kati,UNFILLED | Night: Megan
Day 2: David,Britt | Night: Ashley
Day 3: Josh,Megan | Night: Liz
Day 4: Josh,UNFILLED | Night: Liz
Day 5: Britt,UNFILLED | Night: Ashley
Day 6: Britt,UNFILLED | Night: Ashley
Week: 4
Day 0: Britt,Kati | Night: Ashley
Day 1: Kati,UNFILLED | Night: Josh
Day 2: Megan,UNFILLED | Night: Liz
Day 3: Britt,Josh | Night: Ashley
Day 4: Britt,UNFILLED | Night: Ashley
Day 5: David,Megan | Night: Liz
Day 6: David,Megan | Night: Liz
Week: 5
Day 0: Megan,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Megan,Britt | Night: Liz
Day 4: Megan,UNFILLED | Night: Liz
Day 5: Josh,UNFILLED | Night: Ashley
Day 6: Josh,UNFILLED | Night: Ashley

Starting Score: 280004
Starting greedy initialization...
Epoch 100, current score: 70009, best score: 70009, heat: 95.17
Epoch 200, current score: 70009, best score: 70009, heat: 90.53
Epoch 300, current score: 70009, best score: 70009, heat: 86.11
-----------------Greedy Phase Complete--------------
Greedy best state
Week: 0
Day 0: Josh,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Kati,Josh | Night: Liz
Day 3: Josh,Britt | Night: Ashley
Day 4: Josh,UNFILLED | Night: Ashley
Day 5: David,Kati | Night: Liz
Day 6: David,Kati | Night: Liz
Week: 1
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Josh
Day 2: David,Megan | Night: Ashley
Day 3: Kati,Britt | Night: Liz
Day 4: Kati,UNFILLED | Night: Liz
Day 5: Megan,UNFILLED | Night: Ashley
Day 6: Megan,UNFILLED | Night: Ashley
Week: 2
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Josh,Kati | Night: Liz
Day 3: Megan,Britt | Night: Ashley
Day 4: Megan,UNFILLED | Night: Ashley
Day 5: David,Josh | Night: Liz
Day 6: David,Josh | Night: Liz
Week: 3
Day 0: Josh,Megan | Night: Liz
Day 1: Britt,UNFILLED | Night: Megan
Day 2: David,Megan | Night: Ashley
Day 3: Josh,Megan | Night: Liz
Day 4: Josh,UNFILLED | Night: Liz
Day 5: Britt,UNFILLED | Night: Ashley
Day 6: Britt,UNFILLED | Night: Ashley
Week: 4
Day 0: Britt,Kati | Night: Ashley
Day 1: Kati,UNFILLED | Night: Josh
Day 2: Megan,Kati | Night: Liz
Day 3: Britt,Megan | Night: Ashley
Day 4: Britt,UNFILLED | Night: Ashley
Day 5: David,Megan | Night: Liz
Day 6: David,Megan | Night: Liz
Week: 5
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Britt | Night: Liz
Day 4: Megan,UNFILLED | Night: Liz
Day 5: Josh,UNFILLED | Night: Ashley
Day 6: Josh,UNFILLED | Night: Ashley

Score: 70009
Starting post‑Greedy repair...
Repair: swapped Megan@230 with Kati@100 70009→60009
Repair: swapped Megan@301 with Kati@130 60009→20010
Repair: swapped Megan@100 with Josh@000 20010→20005
Repair: swapped Megan@321 with Josh@300 20005→10005
Finished repairs in 5 No further repairs after 5 epochs
After Repair state
Week: 0
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Kati,Josh | Night: Liz
Day 3: Josh,Britt | Night: Ashley
Day 4: Josh,UNFILLED | Night: Ashley
Day 5: David,Kati | Night: Liz
Day 6: David,Kati | Night: Liz
Week: 1
Day 0: Josh,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Josh
Day 2: David,Megan | Night: Ashley
Day 3: Megan,Britt | Night: Liz
Day 4: Kati,UNFILLED | Night: Liz
Day 5: Megan,UNFILLED | Night: Ashley
Day 6: Megan,UNFILLED | Night: Ashley
Week: 2
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,UNFILLED | Night: Megan
Day 2: Josh,Kati | Night: Liz
Day 3: Kati,Britt | Night: Ashley
Day 4: Megan,UNFILLED | Night: Ashley
Day 5: David,Josh | Night: Liz
Day 6: David,Josh | Night: Liz
Week: 3
Day 0: Megan,Kati | Night: Liz
Day 1: Britt,UNFILLED | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Megan | Night: Liz
Day 4: Josh,UNFILLED | Night: Liz
Day 5: Britt,UNFILLED | Night: Ashley
Day 6: Britt,UNFILLED | Night: Ashley
Week: 4
Day 0: Britt,Kati | Night: Ashley
Day 1: Kati,UNFILLED | Night: Josh
Day 2: Megan,Kati | Night: Liz
Day 3: Britt,Megan | Night: Ashley
Day 4: Britt,UNFILLED | Night: Ashley
Day 5: David,Megan | Night: Liz
Day 6: David,Megan | Night: Liz
Week: 5
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,UNFILLED | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Britt | Night: Liz
Day 4: Megan,UNFILLED | Night: Liz
Day 5: Josh,UNFILLED | Night: Ashley
Day 6: Josh,UNFILLED | Night: Ashley

Score: 10005
-----------------Repair Phase Complete--------------
Filling Minimums...
After Filling state
Week: 0
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,Kati | Night: Megan
Day 2: Kati,Josh | Night: Liz
Day 3: Josh,Britt | Night: Ashley
Day 4: Josh,UNFILLED | Night: Ashley
Day 5: David,Kati | Night: Liz
Day 6: David,Kati | Night: Liz
Week: 1
Day 0: Josh,Britt | Night: Liz
Day 1: Britt,Kati | Night: Josh
Day 2: David,Megan | Night: Ashley
Day 3: Megan,Britt | Night: Liz
Day 4: Kati,Josh | Night: Liz
Day 5: Megan,UNFILLED | Night: Ashley
Day 6: Megan,UNFILLED | Night: Ashley
Week: 2
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,Kati | Night: Megan
Day 2: Josh,Kati | Night: Liz
Day 3: Kati,Britt | Night: Ashley
Day 4: Megan,UNFILLED | Night: Ashley
Day 5: David,Josh | Night: Liz
Day 6: David,Josh | Night: Liz
Week: 3
Day 0: Megan,Kati | Night: Liz
Day 1: Britt,Kati | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Megan | Night: Liz
Day 4: Josh,Kati | Night: Liz
Day 5: Britt,UNFILLED | Night: Ashley
Day 6: Britt,UNFILLED | Night: Ashley
Week: 4
Day 0: Britt,Kati | Night: Ashley
Day 1: Kati,UNFILLED | Night: Josh
Day 2: Megan,Kati | Night: Liz
Day 3: Britt,Megan | Night: Ashley
Day 4: Britt,Josh | Night: Ashley
Day 5: David,Megan | Night: Liz
Day 6: David,Megan | Night: Liz
Week: 5
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,Kati | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Britt | Night: Liz
Day 4: Megan,Kati | Night: Liz
Day 5: Josh,UNFILLED | Night: Ashley
Day 6: Josh,UNFILLED | Night: Ashley

Score: 10000
-----------------Fill Phase Complete--------------
Final Sweep...
Extra abs‐fix pass: 1 absolute violations remain
  swap ABS fix: (331)Megan↔(341)Kati
-----------------Template Complete--------------
Score: 0

--- Final Best Solution ---
Week: 0
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,Kati | Night: Megan
Day 2: Kati,Josh | Night: Liz
Day 3: Josh,Britt | Night: Ashley
Day 4: Josh,UNFILLED | Night: Ashley
Day 5: David,Kati | Night: Liz
Day 6: David,Kati | Night: Liz
Week: 1
Day 0: Josh,Britt | Night: Liz
Day 1: Britt,Kati | Night: Josh
Day 2: David,Megan | Night: Ashley
Day 3: Megan,Britt | Night: Liz
Day 4: Kati,Josh | Night: Liz
Day 5: Megan,UNFILLED | Night: Ashley
Day 6: Megan,UNFILLED | Night: Ashley
Week: 2
Day 0: Megan,Britt | Night: Ashley
Day 1: Britt,Kati | Night: Megan
Day 2: Josh,Kati | Night: Liz
Day 3: Kati,Britt | Night: Ashley
Day 4: Megan,UNFILLED | Night: Ashley
Day 5: David,Josh | Night: Liz
Day 6: David,Josh | Night: Liz
Week: 3
Day 0: Megan,Kati | Night: Liz
Day 1: Britt,Kati | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Kati | Night: Liz
Day 4: Josh,Megan | Night: Liz
Day 5: Britt,UNFILLED | Night: Ashley
Day 6: Britt,UNFILLED | Night: Ashley
Week: 4
Day 0: Britt,Kati | Night: Ashley
Day 1: Kati,UNFILLED | Night: Josh
Day 2: Megan,Kati | Night: Liz
Day 3: Britt,Megan | Night: Ashley
Day 4: Britt,Josh | Night: Ashley
Day 5: David,Megan | Night: Liz
Day 6: David,Megan | Night: Liz
Week: 5
Day 0: Kati,Britt | Night: Liz
Day 1: Britt,Kati | Night: Megan
Day 2: David,Josh | Night: Ashley
Day 3: Josh,Britt | Night: Liz
Day 4: Megan,Kati | Night: Liz
Day 5: Josh,UNFILLED | Night: Ashley
Day 6: Josh,UNFILLED | Night: Ashley

Global Abs Violation: 0
Global Rel Violation: 0
Staff Abs Violation: 0
Staff Rel Violation: 0
Final Score: 0
UNFILLED: 108 hrs worked total
David: 108 hrs worked total
Josh: 216 hrs worked total
Kati: 216 hrs worked total
Britt: 216 hrs worked total
Liz: 216 hrs worked total
Megan: 216 hrs worked total
Ashley: 216 hrs worked total
UNFILLED:
  Weeks 0-1: 36 hrs
  Weeks 2-3: 36 hrs
  Weeks 4-5: 36 hrs
David:
  Weeks 0-1: 36 hrs
  Weeks 2-3: 36 hrs
  Weeks 4-5: 36 hrs
Josh:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
Kati:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
Britt:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
Liz:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
Megan:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
Ashley:
  Weeks 0-1: 72 hrs
  Weeks 2-3: 72 hrs
  Weeks 4-5: 72 hrs
</details>```

![Score by Epoch chart showing improvement over training](Results/Score_by_Epoch.png)  

# Results and Conclusion
The model reliably generates schedule templates that satisfy both global and employee-level constraints in most runs. This significantly reduces the effort compared to manual schedule creation. Any dissatisfaction with the output can typically be resolved by encoding additional constraints or adjusting the scoring logic accordingly.

# Future Work and Extension  
This solution addresses one half of the sponsor’s problem—template creation. The other half involved mapping the template to an annual calendar. I have already created a separate solution for that task (see the "Scheduler" on GitHub). A natural next step would be to integrate both tools into a unified workflow.

# References  

No external sources were used. However, LLM queries assisted with architectural design and debugging.  

# Contributing  
No external parties contibuted to this project.  