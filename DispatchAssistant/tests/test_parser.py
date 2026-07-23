from app.parser import parse_ticket


def main():

    print("=" * 50)
    print("Industrial Programmer - Parser Test")
    print("=" * 50)

    with open("logs/sygap.html", "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_ticket(html)

    print("\nRequest Number")
    print("--------------------")
    print(result["request_number"])

    print("\nIncident List")
    print("--------------------")

    if len(result["incident_list"]) == 0:

        print("Tidak ada Incident ditemukan.")

    else:

        for i, inc in enumerate(result["incident_list"], start=1):
            print(f"{i}. {inc}")

    print("\nJumlah Incident :", len(result["incident_list"]))


if __name__ == "__main__":
    main()