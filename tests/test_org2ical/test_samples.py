"""
Test samples found online
"""

import textwrap

from .utils import iCalEntry, compare


# Ref: https://orgmode.org/manual/Deadlines-and-Scheduling.html
def test_Deadlines_and_Scheduling():
    org_str = textwrap.dedent("""\
    *** TODO write article about the Earth for the Guide
        DEADLINE: <2004-02-29 Sun>
        The editor in charge is [[bbdb:Ford Prefect]]
    *** TODO Call Trillian for a date on New Years Eve.
        SCHEDULED: <2004-12-25 Sat>
    """)
    icals = [
        iCalEntry("2004-02-29", None, "write article about the Earth for the Guide", "    The editor in charge is bbdb:Ford Prefect", "DEADLINE"),
        iCalEntry("2004-12-25", None, "Call Trillian for a date on New Years Eve.", "", "SCHEDULED"),
    ]
    compare(org_str, icals)

# Ref: https://orgmode.org/manual/Clocking-Work-Time.html
def test_Clocking_Work_Time():
    pass

# Ref: https://orgmode.org/manual/Timestamps.html
def test_Timestamps():
    org_str = textwrap.dedent("""\
    * Meet Peter at the movies
      <2006-11-01 Wed 19:15>
    * Discussion on climate change
      <2006-11-02 Thu 20:00-22:00>
    * Pick up Sam at school
      <2007-05-16 Wed 12:30 +1w>
    * Meetings
    ** Meeting in Amsterdam
       <2004-08-23 Mon>--<2004-08-26 Thu>
    * Gillian comes late for the fifth time
      [2006-11-01 Wed]
    * Test day  <2025-02-05 Wed>
    * Test time  <2025-02-05 Wed 09:30>
    * Test duration <2025-02-05 Wed 09:30-11:30>
    * Test time2  <2025-02-05 Wed 9:30>
    * Test duration2 <2025-02-05 Wed 9:30-11:30>
    * Test duration3 <2025-02-05 Wed 8:30-9:30>
    """)
    icals = [
        iCalEntry("2006-11-01 19:15:00+00:00", "2006-11-01 20:15:00+00:00", "Meet Peter at the movies", "  <2006-11-01 Wed 19:15>", "TIMESTAMP"),
        iCalEntry("2006-11-02 20:00:00+00:00", "2006-11-02 22:00:00+00:00", "Discussion on climate change", "  <2006-11-02 Thu 20:00-22:00>", "TIMESTAMP"),
        iCalEntry("2007-05-16 12:30:00+00:00", "2007-05-16 13:30:00+00:00", "Pick up Sam at school", "  <2007-05-16 Wed 12:30 +1w>", "TIMESTAMP", "FREQ=WEEKLY;INTERVAL=1"),
        iCalEntry("2004-08-23", "2004-08-27", "Meeting in Amsterdam", "   <2004-08-23 Mon>--<2004-08-26 Thu>", "TIMESTAMP", parents=["Meetings"]),
        iCalEntry("2025-02-05", None, "Test day  <2025-02-05 Wed>", "", "TIMESTAMP", path_override="Test day  <2025-02-05 Wed>"),
        iCalEntry("2025-02-05 09:30:00+00:00", "2025-02-05 10:30:00+00:00", "Test time  <2025-02-05 Wed 09:30>", "", "TIMESTAMP", path_override="Test time  <2025-02-05 Wed 09:30>"),
        iCalEntry("2025-02-05 09:30:00+00:00", "2025-02-05 11:30:00+00:00", "Test duration <2025-02-05 Wed 09:30-11:30>", "", "TIMESTAMP", path_override="Test duration <2025-02-05 Wed 09:30-11:30>"),
        iCalEntry("2025-02-05 09:30:00+00:00", "2025-02-05 10:30:00+00:00", "Test time2  <2025-02-05 Wed 09:30>", "", "TIMESTAMP", path_override="Test time2  <2025-02-05 Wed 09:30>"),
        iCalEntry("2025-02-05 09:30:00+00:00", "2025-02-05 11:30:00+00:00", "Test duration2 <2025-02-05 Wed 09:30-11:30>", "", "TIMESTAMP", path_override="Test duration2 <2025-02-05 Wed 09:30-11:30>"),
        iCalEntry("2025-02-05 08:30:00+00:00", "2025-02-05 09:30:00+00:00", "Test duration3 <2025-02-05 Wed 08:30-09:30>", "", "TIMESTAMP", path_override="Test duration3 <2025-02-05 Wed 08:30-09:30>"),
    ]
    compare(org_str, icals)

# Ref: https://orgmode.org/manual/Repeated-tasks.html
def test_Repeated_tasks():
    org_str = textwrap.dedent("""\
    * My Todos
    ** TODO Pay the rent
       DEADLINE: <2005-10-01 Sat +1m>
    ** TODO Pay the rent (with warning)
       DEADLINE: <2005-10-01 Sat +1m -3d>
    ** TODO Pay the rent
       DEADLINE: <2005-11-01 Tue +1m>
    ** TODO Call Father
       DEADLINE: <2008-02-10 Sun ++1w>
       Marking this DONE shifts the date by at least one week, but also
       by as many weeks as it takes to get this date into the future.
       However, it stays on a Sunday, even if you called and marked it
       done on Saturday.
    ** TODO Empty kitchen trash
       DEADLINE: <2008-02-08 Fri 20:00 ++1d>
       Marking this DONE shifts the date by at least one day, and also
       by as many days as it takes to get the timestamp into the future.
       Since there is a time in the timestamp, the next deadline in the
       future will be on today's date if you complete the task before
       20:00.
    ** TODO Check the batteries in the smoke detectors
       DEADLINE: <2005-11-01 Tue .+1m>
       Marking this DONE shifts the date to one month after today.
    ** TODO Wash my hands
       DEADLINE: <2019-04-05 08:00 Fri .+1h>
       Marking this DONE shifts the date to exactly one hour from now
    """)
    icals = [
        iCalEntry("2005-10-01", None, "Pay the rent", "", "DEADLINE", "FREQ=MONTHLY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2005-10-01", None, "Pay the rent (with warning)", "", "DEADLINE", "FREQ=MONTHLY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2005-11-01", None, "Pay the rent", "", "DEADLINE", "FREQ=MONTHLY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2008-02-10", None, "Call Father", """\
   Marking this DONE shifts the date by at least one week, but also
   by as many weeks as it takes to get this date into the future.
   However, it stays on a Sunday, even if you called and marked it
   done on Saturday.""", "DEADLINE", "FREQ=WEEKLY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2008-02-08 20:00:00+00:00", None, "Empty kitchen trash", """\
   Marking this DONE shifts the date by at least one day, and also
   by as many days as it takes to get the timestamp into the future.
   Since there is a time in the timestamp, the next deadline in the
   future will be on today's date if you complete the task before
   20:00.""", "DEADLINE", "FREQ=DAILY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2005-11-01", None, "Check the batteries in the smoke detectors", "   Marking this DONE shifts the date to one month after today.", "DEADLINE", "FREQ=MONTHLY;INTERVAL=1", parents=["My Todos"]),
        iCalEntry("2019-04-05 08:00:00+00:00", None, "Wash my hands", "   Marking this DONE shifts the date to exactly one hour from now", "DEADLINE", "FREQ=HOURLY;INTERVAL=1", parents=["My Todos"]),
    ]
    compare(org_str, icals)


def test_Birthday_tasks():
    org_str = textwrap.dedent("""\
    * Contacts
    ** Grandfather
    :PROPERTIES:
    :CREATED:  [2021-04-18 Mon 15:09]
    :BIRTHDAY: 1934-05-02
    :ID:       bla
    :END:
    """)
    icals = [
        iCalEntry("1934-05-02", None, "Grandfather Birthday", '- Birthyear: 1934\n- Age 2021: 87', "BIRTHDAY", "FREQ=YEARLY;INTERVAL=1", path=False),
    ]
    compare(org_str, icals, include_types={"BIRTHDAY"})


def test_diaryfloat_tasks():
    org_str = textwrap.dedent("""\
    * Calendar
    ** Last Monday of every month
      <%%(diary-float t 1 -1)>
    ** Every 2nd Tuesday
      <%%(diary-float t 2 2)>
    ** 19:00-23:00 STG
      <%%(diary-float t 2 2)>
    ** STG2
      <%%(diary-float t 2 2) 19:00>
    ** STG3
      <%%(diary-float t 2 2) 19:00-23:00>""")
    
    # FREQ=MONTHLY;BYSETPOS=-1;BYDAY=MO;INTERVAL=1
    # FREQ=MONTHLY;BYSETPOS=2;BYDAY=TU;INTERVAL=1

    # new diary-float syntax since org 9.7: https://orgmode.org/Changes.html#org5446bd7

    icals = [
        iCalEntry("1985-01-01", None, "Last Monday of every month", "  <%%(diary-float t 1 -1)>", "REGULAR", "FREQ=MONTHLY;INTERVAL=1;BYDAY=MO;BYSETPOS=-1", parents=["Calendar"]),
        iCalEntry("1985-01-01", None, "Every 2nd Tuesday",          "  <%%(diary-float t 2 2)>", "REGULAR", "FREQ=MONTHLY;INTERVAL=1;BYDAY=TU;BYSETPOS=2", parents=["Calendar"]),
        iCalEntry("1985-01-01 19:00:00+01:00", "1985-01-01 23:00:00+01:00", "STG",          "  <%%(diary-float t 2 2)>", "REGULAR", "FREQ=MONTHLY;INTERVAL=1;BYDAY=TU;BYSETPOS=2", parents=["Calendar"], path_override="19:00-23:00 STG"),
        iCalEntry("1985-01-01 19:00:00+01:00", "1985-01-01 20:00:00+01:00", "STG2",          "  <%%(diary-float t 2 2) 19:00>", "REGULAR", "FREQ=MONTHLY;INTERVAL=1;BYDAY=TU;BYSETPOS=2", parents=["Calendar"]),
        iCalEntry("1985-01-01 19:00:00+01:00", "1985-01-01 23:00:00+01:00", "STG3",          "  <%%(diary-float t 2 2) 19:00-23:00>", "REGULAR", "FREQ=MONTHLY;INTERVAL=1;BYDAY=TU;BYSETPOS=2", parents=["Calendar"]),
    ]

    compare(org_str, icals, include_types={"DIARY"})
