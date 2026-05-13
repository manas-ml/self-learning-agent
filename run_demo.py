import sys
from pathlib import Path

import config
from agent.core import SQLLearningAgent
from agent.sql_executor import SQLExecutor

BROKEN_QUERIES = [
    # syntax_error — trailing comma before FROM
    "SELECT name, price, FROM products",
    # no_such_column — typo in column name
    "SELECT name, pric FROM products",
    # no_such_table — typo in table name
    "SELECT * FROM product WHERE price > 10",
    # no_such_column — wrong column name in customers
    "SELECT customer_name, email FROM customers",
    # ambiguous_column — unqualified 'id' in a JOIN
    "SELECT id, name FROM customers JOIN orders ON customers.id = orders.customer_id",
]


def _divider(char="─", width=70):
    print(char * width)


def _print_result(result: dict, idx: int) -> None:
    success_label = "SUCCESS" if result["success"] else "GAVE UP"
    _divider()
    print(f"Query {idx}  [{success_label}]  ({result['iterations']} iteration(s))")
    _divider("-")
    print(f"  Original : {result['original_query']}")
    print(f"  Fixed    : {result['final_query']}")
    print(f"  Errors   : {', '.join(result['error_types_seen']) or 'none'}")
    if result["skill_created_or_updated"]:
        print(f"  Skill    : skills/{result['skill_created_or_updated']}.md  (created/updated)")
    if result["success"]:
        print(f"  Rows     : {result['rows_returned']}")


def main() -> None:
    print("\n=== Self-Learning SQL Agent Demo ===\n")

    # Bootstrap sample database
    executor = SQLExecutor(config.SAMPLE_DB_PATH)
    executor.setup_sample_db()
    executor.close()
    print(f"Sample DB ready at {config.SAMPLE_DB_PATH}\n")

    agent = SQLLearningAgent()

    results = []
    for i, query in enumerate(BROKEN_QUERIES, 1):
        print(f"\n[Query {i}/{len(BROKEN_QUERIES)}] {query}")
        result = agent.improve(query)
        _print_result(result, i)
        results.append(result)

    # Summary
    _divider("═")
    print("\nFINAL SUMMARY\n")

    succeeded = sum(1 for r in results if r["success"])
    print(f"Queries fixed: {succeeded}/{len(results)}\n")

    print("Error Pattern Memory:")
    for stat in agent.memory.get_error_stats():
        print(f"  {stat['error_type']:30s}  occurrences={stat['occurrences']}")

    print("\nGenerated Skills:")
    skills = agent.skills.list_skills()
    if skills:
        for s in skills:
            print(
                f"  {s.get('name','?'):30s}  "
                f"uses={s.get('usage_count',0)}  "
                f"success_rate={s.get('success_rate',0.0):.0%}"
            )
    else:
        print("  (none yet)")

    _divider("═")
    print("\nRun again to see the agent reuse its learned skills and past examples.\n")


if __name__ == "__main__":
    if not Path("agent").exists():
        print("Run from the self-learning-agent/ directory.", file=sys.stderr)
        sys.exit(1)
    main()
