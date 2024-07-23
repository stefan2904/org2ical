from datetime import datetime, timezone
from typing import List, Set

import icalendar

import org2ical


class iCalEntry():
    def __init__(
        self,
        dtstart: datetime,
        dtend: datetime,
        summary: str,
        description: str,
        categories: Set[str],
        rrule: str = "",
        *,
        parents: List[str] = None,
        path: bool = True,
        path_override: str = None,
    ):
        self.dtstart = dtstart
        self.dtend = dtend
        #if self.dtend is None:
        #    self.dtend = self.dtstart
        self.summary = summary
        self.description = description
        self.categories = categories
        self.rrule = rrule
        parents = parents
        if parents is None:
            parents = []
        if self.description != "":
            self.description += "\n\n"
        if path:
            self.description += "Org Path: " + " > ".join(parents + [path_override if path_override else self.summary])

def compare(org_str: str, icals: List[iCalEntry], warnings=[], *,
        prod_id: str = "-//j3soon//org2ical//EN",
        now: datetime = datetime(2021, 1, 1, 0, 0, 0, 0, timezone.utc),
        categories: Set[str] = None,
        ignore_states: Set[str] = None,
        ignore_tags: Set[str] = None,
        include_types: Set[str] = None,
        from_tz: timezone = timezone.utc,
        to_tz: timezone = timezone.utc,
    ):
    ical_str, warnings_ = org2ical.loads(
        org_str,
        prod_id=prod_id,
        now=now,
        categories=categories,
        ignore_states=ignore_states,
        ignore_tags=ignore_tags,
        include_types=include_types,
        from_tz=from_tz,
        to_tz=to_tz,
    )
    cal = icalendar.Calendar.from_ical(ical_str)
    now = now.replace(tzinfo=to_tz)
    now = now.astimezone(tz=from_tz)
    now = now.replace(tzinfo=timezone.utc)
    i = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            print(f"[{i}]")
            #allDayEvent = 'VALUE' in component['dtstart'].params and component['dtstart'].params['VALUE'] == "DATE"
            # print("Expected:", str(component['dtstamp'].dt))
            # print("Actual  :", str(now))
            assert str(component['dtstamp'].dt) == str(now)
            assert component['uid'] != ""
            ical = icals[i]
            print("Expected Start:", ical.dtstart)
            print("Actual   Start:", str(component['dtstart'].dt))
            if ical.dtend:
                print("Expected End:  ", ical.dtend)
                print("Actual   End:  ", str(component['dtend'].dt if 'dtend' in component else 'None'))
            print("Expected:", ical.summary)
            print("Actual  :", component['summary'])
            print("Expected:", ical.description.encode())
            print("Actual  :", component['description'].encode())
            print("Expected:", ical.categories)
            print("Actual  :", component['categories'].to_ical().decode("utf-8"))
            assert str(component['dtstart'].dt) == ical.dtstart
            if ical.dtend: # end time expected
                assert 'dtend' in component
                assert str(component['dtend'].dt) == ical.dtend
            assert component['summary'] == ical.summary
            assert component['description'] == ical.description
            assert component['categories'].to_ical().decode("utf-8") == ical.categories
            rrule = ""
            if 'RRULE' in component:
                rrule = component['RRULE'].to_ical().decode("utf-8")
            print("Expected:", ical.rrule)
            print("Actual  :", rrule)
            assert rrule == ical.rrule
            i += 1
    print("Expected Len:", len(icals))
    print("Actual Len  :", i)
    assert i == len(icals)
    print("Expected Warnings:", warnings)
    print("Actual Warnings  :", warnings_)
    assert warnings_ == warnings
