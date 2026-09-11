import difflib

names1 = ["นาย สมชาย รักดี", "น.ส. สมหญิง สวยงาม", "บจก. เทสติ้ง"]
names2 = ["นาย สมชาย รักดี", "นาง สมหญิง สวยงาม", "บมจ. เทสติ้ง"]

for n1 in names1:
    for n2 in names2:
        if n1 != n2:
            r = difflib.SequenceMatcher(None, n1, n2).ratio()
            print(f"{n1} -> {n2}: {r:.2f}")
