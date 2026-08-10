import csv
import random
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
OPEN_MINUTES = 7.5 * 60  # 9:00 a.m. to 4:30 p.m.
SEED = 42
OUTPUT_DIR = Path("registration_results")
GRAPH_DIR = OUTPUT_DIR / "graphs"
DAILY_RANGES = {
    1: (3, 5),      # observed approximately 4
    2: (5, 7),      # observed approximately 6
    3: (13, 17),    # observed approximately 15
    4: (19, 25),    # observed approximately 22
    5: (18, 22),    # observed approximately 20
    6: (23, 29),    # observed approximately 26
    7: (27, 33),    # observed approximately 30; busiest day
}

def process_stage(arrivals, service_min, service_max, servers, rng):
    available = [0.0] * servers
    result = {}

    for student_id, arrival_time in sorted(arrivals, key=lambda x: x[1]):
        server = min(range(servers), key=lambda i: available[i])
        start = max(arrival_time, available[server])
        wait = start - arrival_time
        service = rng.uniform(service_min, service_max)
        finish = start + service
        available[server] = finish

        result[student_id] = {
            "arrival": arrival_time,
            "start": start,
            "finish": finish,
            "wait": wait,
            "service": service,
        }

    return result

def maximum_queue(records):
    events = []
    for record in records.values():
        events.append((record["arrival"], 1))
        events.append((record["start"], -1))

    events.sort(key=lambda x: (x[0], x[1]))
    queue = 0
    maximum = 0

    for _, change in events:
        queue = max(0, queue + change)
        maximum = max(maximum, queue)

    return maximum

def simulate_day(day, count, registration_servers, configuration, seed):
    rng = random.Random(seed)

    arrivals = [
        (student_id, rng.uniform(0, OPEN_MINUTES))
        for student_id in range(1, count + 1)
    ]

    counselling = process_stage(arrivals, 0.5, 1.0, 1, rng)

    registration_arrivals = [
        (student_id, record["finish"])
        for student_id, record in counselling.items()
    ]
    registration = process_stage(
        registration_arrivals, 12.0, 18.0, registration_servers, rng
    )

    approval_arrivals = [
        (student_id, record["finish"])
        for student_id, record in registration.items()
    ]
    approval = process_stage(approval_arrivals, 10.0, 15.0, 1, rng)

    detail_rows = []

    for student_id, initial_arrival in arrivals:
        c = counselling[student_id]
        r = registration[student_id]
        a = approval[student_id]
        total_wait = c["wait"] + r["wait"] + a["wait"]
        total_process = a["finish"] - initial_arrival

        detail_rows.append({
            "day": day,
            "configuration": configuration,
            "student_id": student_id,
            "daily_student_count": count,
            "arrival_minute_after_9am": round(initial_arrival, 2),
            "counselling_form_wait_minutes": round(c["wait"], 2),
            "counselling_form_service_minutes": round(c["service"], 2),
            "registration_queue_wait_minutes": round(r["wait"], 2),
            "registration_service_minutes": round(r["service"], 2),
            "approval_queue_wait_minutes": round(a["wait"], 2),
            "approval_service_minutes": round(a["service"], 2),
            "total_wait_minutes": round(total_wait, 2),
            "whole_process_minutes": round(total_process, 2),
            "completed_by_4_30pm": "Yes" if a["finish"] <= OPEN_MINUTES else "No",
        })

    summary = {
        "day": day,
        "configuration": configuration,
        "students": count,
        "average_counselling_wait_minutes": statistics.mean(
            row["counselling_form_wait_minutes"] for row in detail_rows
        ),
        "average_registration_wait_minutes": statistics.mean(
            row["registration_queue_wait_minutes"] for row in detail_rows
        ),
        "average_approval_wait_minutes": statistics.mean(
            row["approval_queue_wait_minutes"] for row in detail_rows
        ),
        "average_total_wait_minutes": statistics.mean(
            row["total_wait_minutes"] for row in detail_rows
        ),
        "average_whole_process_minutes": statistics.mean(
            row["whole_process_minutes"] for row in detail_rows
        ),
        "maximum_registration_queue": maximum_queue(registration),
        "maximum_approval_queue": maximum_queue(approval),
        "registration_utilization_percent": (
            sum(x["service"] for x in registration.values())
            / (registration_servers * OPEN_MINUTES)
            * 100
        ),
        "approval_utilization_percent": (
            sum(x["service"] for x in approval.values())
            / OPEN_MINUTES
            * 100
        ),
        "completed_by_4_30pm_percent": (
            sum(row["completed_by_4_30pm"] == "Yes" for row in detail_rows)
            / count
            * 100
        ),
    }

    return detail_rows, summary

def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

def create_graphs(daily_summary, day7_comparison):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    days = [row["day"] for row in daily_summary]

    def save_bar(filename, title, values, ylabel, color="steelblue"):
        plt.figure(figsize=(9, 5))
        bars = plt.bar(days, values, color=color)
        plt.title(title)
        plt.xlabel("Registration day")
        plt.ylabel(ylabel)
        plt.xticks(days)
        for bar, value in zip(bars, values):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                     f"{value:.1f}", ha="center", va="bottom", fontsize=8)
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / filename, dpi=300)
        plt.close()

    save_bar(
        "daily_student_arrivals.png",
        "Simulated Student Arrivals by Day",
        [row["students"] for row in daily_summary],
        "Students",
    )
    save_bar(
        "average_total_waiting_time.png",
        "Average Total Waiting Time by Day",
        [row["average_total_wait_minutes"] for row in daily_summary],
        "Waiting time (minutes)",
        "darkorange",
    )
    save_bar(
        "average_whole_process_time.png",
        "Average Whole Registration Process Time",
        [row["average_whole_process_minutes"] for row in daily_summary],
        "Process time (minutes)",
        "seagreen",
    )

    x = range(1, 8)
    width = 0.25
    plt.figure(figsize=(9, 5))
    plt.bar([i - width for i in x],
            [row["average_counselling_wait_minutes"] for row in daily_summary],
            width, label="Counselling form")
    plt.bar(x,
            [row["average_registration_wait_minutes"] for row in daily_summary],
            width, label="Registration")
    plt.bar([i + width for i in x],
            [row["average_approval_wait_minutes"] for row in daily_summary],
            width, label="Approval")
    plt.title("Average Waiting Time at Each Stage")
    plt.xlabel("Registration day")
    plt.ylabel("Waiting time (minutes)")
    plt.xticks(list(x))
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / "stage_waiting_time.png", dpi=300)
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(days, [row["maximum_registration_queue"] for row in daily_summary],
             marker="o", label="Registration queue")
    plt.plot(days, [row["maximum_approval_queue"] for row in daily_summary],
             marker="s", label="Approval queue")
    plt.title("Maximum Queue Length by Day")
    plt.xlabel("Registration day")
    plt.ylabel("Students")
    plt.xticks(days)
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / "maximum_queue_length.png", dpi=300)
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(days, [row["registration_utilization_percent"] for row in daily_summary],
             marker="o", label="Registration officer")
    plt.plot(days, [row["approval_utilization_percent"] for row in daily_summary],
             marker="s", label="Approval officer")
    plt.title("Officer Utilization by Day")
    plt.xlabel("Registration day")
    plt.ylabel("Utilization (%)")
    plt.xticks(days)
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / "officer_utilization.png", dpi=300)
    plt.close()

    labels = ["One registration officer", "Two registration officers"]
    values = [
        day7_comparison["one_officer"]["average_total_wait_minutes"],
        day7_comparison["two_officers"]["average_total_wait_minutes"],
    ]
    plt.figure(figsize=(8, 5))
    plt.bar(labels, values, color=["firebrick", "royalblue"])
    plt.title("Day 7 Improvement: Registration Staffing")
    plt.ylabel("Average total waiting time (minutes)")
    plt.xticks(rotation=10)
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / "day7_staffing_comparison.png", dpi=300)
    plt.close()
count_rng = random.Random(SEED)
daily_counts = [
    count_rng.randint(low, high)
    for low, high in DAILY_RANGES.values()
]
if daily_counts[6] <= max(daily_counts[:6]):
    daily_counts[6] = max(daily_counts[:6]) + 1

all_details = []
daily_summary = []
day7_comparison = {}
for day, count in enumerate(daily_counts, start=1):
    details, summary = simulate_day(
        day, count, 1, "Base system: one officer at registration", SEED + day
    )
    all_details.extend(details)
    daily_summary.append(summary)
day7 = daily_counts[6]
base_details, base_summary = simulate_day(
    7, day7, 1, "Day 7 improvement: one registration officer", SEED + 700
)
improved_details, improved_summary = simulate_day(
    7, day7, 2, "Day 7 improvement: two registration officers", SEED + 700
)
all_details.extend(base_details)
all_details.extend(improved_details)
day7_comparison = {
    "one_officer": base_summary,
    "two_officers": improved_summary,
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
save_csv(OUTPUT_DIR / "student_registration_dataset.csv", all_details)
save_csv(OUTPUT_DIR / "daily_performance_summary.csv", daily_summary)
save_csv(
    OUTPUT_DIR / "day7_staffing_comparison.csv",
    [base_summary, improved_summary],
)
create_graphs(daily_summary, day7_comparison)

print("Simulation completed.")
print("Random daily student counts:", daily_counts)
print("Total students in the seven-day base dataset:", sum(daily_counts))
print("Detailed CSV:", OUTPUT_DIR / "student_registration_dataset.csv")
print("Summary CSV:", OUTPUT_DIR / "daily_performance_summary.csv")
print("Day 7 comparison CSV:", OUTPUT_DIR / "day7_staffing_comparison.csv")
print("Graphs folder:", GRAPH_DIR)