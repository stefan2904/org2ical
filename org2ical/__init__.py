"""Converts a org-mode string to an iCalendar string."""

# pylint: disable=too-many-locals
# pylint: disable=too-many-arguments
# pylint: disable=protected-access
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
import hashlib
import textwrap
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Set, Tuple, Union
import re

import orgparse

DEADLINE = 'DEADLINE'
SCHEDULED = 'SCHEDULED'
TIMESTAMP = 'TIMESTAMP'
CLOCK = 'CLOCK'
BIRTHDAY = 'BIRTHDAY'
DIARY = 'DIARY'
# Ignore inactive timestamps


def loads(
        org_str: str,
        *,
        prod_id: str = "-//stefan2904//org2ical//EN",
        now: datetime = datetime.now(tz=timezone.utc),
        categories: Optional[Set[str]] = None,
        ignore_states: Optional[Set[str]] = None,
        ignore_tags: Optional[Set[str]] = None,
        include_types: Optional[Set[str]] = None,
        from_tz: timezone = timezone.utc,
        to_tz: timezone = timezone.utc,
        todo_states: Optional[List[str]] = None,
        done_states: Optional[List[str]] = None,
        just_entries: bool = False,
        mytimezone: str = "",
        ) -> Tuple[str, List[str]]:
    """Returns the generated ical string and a list of warnings."""

    mytimezone = """
BEGIN:VTIMEZONE
TZID:Europe/Vienna
X-LIC-LOCATION:Europe/Vienna
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19810329T020000
RRULE:FREQ=YEARLY;UNTIL=20370329T010000Z;BYDAY=-1SU;BYMONTH=3
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19961027T030000
RRULE:FREQ=YEARLY;UNTIL=20361026T010000Z;BYDAY=-1SU;BYMONTH=10
END:STANDARD
END:VTIMEZONE"""

    categories = (categories if categories is not None
                  else set())
    ignore_states = (ignore_states if ignore_states is not None
                     else {"DONE", "CANCELED"})
    ignore_tags = (ignore_tags if ignore_tags is not None
                   else {"ARCHIVE"})
    include_types = (include_types if include_types is not None
                     else {DEADLINE, SCHEDULED, TIMESTAMP})
    diff = include_types - {DEADLINE, SCHEDULED, TIMESTAMP, CLOCK, BIRTHDAY, DIARY}
    todo_states = (todo_states if todo_states is not None
                   else ["TODO"])
    done_states = (done_states if done_states is not None
                   else ["DONE"])
    if len(diff) > 0:
        raise ValueError(f"Invalid include_types: {diff}")

    def _encode_datetime(dt: datetime) -> str:
        """Encodes a datetime object into an iCalendar-compatible string."""
        # The replacement here is reversed to mitigate the time difference.
        dt = dt.replace(tzinfo=to_tz)
        dt = dt.astimezone(tz=from_tz)
        return dt.strftime("%Y%m%dT%H%M%SZ")

    def _encode_date(d: Union[date, datetime], is_range_end=False) -> str:
        """Encodes a date or datetime object into an iCalendar-compatible
        string."""
        if isinstance(d, datetime):
            return _encode_datetime(d)
        if is_range_end:
            d += timedelta(days=1)
        return d.strftime("%Y%m%d")

    def _encode_rrule(cookie: Tuple[str, str, str]) -> str:
        """Encodes a repeater tuple into an iCalendar-compatible string."""
        if cookie is None:
            return ""
        assert len(cookie) == 3
        repeater = cookie[0]
        # This 3 repeaters all mean the same thing during parsing
        assert repeater in ['+', '++', '.+']
        interval = cookie[1]
        freq = {
            'h': 'HOURLY',
            'd': 'DAILY',
            'w': 'WEEKLY',
            'm': 'MONTHLY',
            'y': 'YEARLY'
        }[cookie[2]]
        return f"RRULE:FREQ={freq};INTERVAL={interval}"

    def _node_is_ignored(node: orgparse.OrgNode) -> bool:
        """Determines if a node should be ignored."""
        assert ignore_states is not None
        assert ignore_tags is not None
        if ignore_states.intersection([node.todo]):
            return True
        if ignore_tags.intersection(node.tags):
            return True
        # Check manually since orgparse doesn't support custom Todo states
        if node.todo is not None:
            return False
        for s in ignore_states:
            if node.heading.startswith(s):
                if len(node.heading) > len(s) and node.heading[len(s)] == " ":
                    return True
        return False

    def _node_full_path(node: orgparse.OrgNode) -> str:
        """Returns the full path of a node with ` > ` as delimiter."""
        headings = []
        while node != source:
            headings.append(node.heading)
            node = node.parent
        headings.reverse()
        return " > ".join(headings)

    def _construct_warning(node: orgparse.OrgNode, message: str) -> str:
        """Helper function for constructing warning messages."""
        return textwrap.dedent(
            f"""WARNING: {message} in node: `{_node_full_path(node)}`.""")

    def _node_get_diaries(node: orgparse.OrgNode) -> List[str]:
        diaries = []
        # TODO: better error handling in case of malformed diary-float
        if "<%%(diary-float" in node.heading:
            d = re.findall(r'<%%\(diary-float\s+.*\)>', node.heading)[0]
            diaries.append(d)
        for line in node.body.split("\n"):
            if line.strip().startswith("<%%(diary-float"):
                d = re.findall(r'<%%\(diary-float\s+.*\)>', line)[0]
                diaries.append(d)
        return diaries

    def _encode_diary_to_rrule(diary: str) -> str:
        # <%%(diary-float t 2 2)>
        m = re.search(r'<%%\(diary-float\s([t\+\-\d]*)\s([\+\-\d]*)\s([\+\-\d]*)\)>', diary)
        if not m:
            return None
        month = m.group(1)
        if month != "t":
            # TODO: Implement non-montly diary-float
            return None
        weekday = m.group(2)
        pos = m.group(3)
        day = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"][int(weekday)]
        # FREQ=MONTHLY;BYSETPOS=-1;BYDAY=MO;INTERVAL=1
        return f"RRULE:FREQ=MONTHLY;BYSETPOS={pos};BYDAY={day};INTERVAL=1"

    def _parse_diary_time(diary: str) -> Tuple[str, str, str]:
        # 19:00-23:00 STG
        m = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2}) (.*)', diary)
        if m:
            return m.group(1).replace(':', ''), m.group(2).replace(':', ''), m.group(3).strip()
        m = re.search(r'(\d{2}:\d{2})', diary)
        if m:
            return m.group(1).replace(':', ''), None, m.group(3).strip()
        return None, None, None


    def _construct_vevent(
            now: str,
            startutc: str,
            endutc: str,
            summary: str,
            description: str,
            categories: Set[str],
            *,
            rrule: str = "",
            is_dayevent: bool = False,
            ) -> str:
        startutc = "DTSTART;VALUE=DATE:{}".format(startutc) if is_dayevent else "DTSTART:{}".format(startutc)
        endutc = "DTEND:{}".format(endutc) if endutc else ''
        """Constructs an iCaldendar VEVENT entry string."""
        description = description.replace("\r\n", "\n").replace("\n", "\\n")
        entry_begin = f"""
        BEGIN:VEVENT
        DTSTAMP:{now}
        """.strip()
        entry_mid = f"""
        {startutc}
        {endutc}
        SUMMARY:{summary}
        DESCRIPTION:{description}
        CATEGORIES:{",".join(categories)}
        {rrule}
        """.strip()
        entry_end = """
        END:VEVENT
        """.strip()
        md5hash = hashlib.md5((entry_begin + entry_mid + entry_end)
                              .encode('utf-8')).hexdigest()
        entry = textwrap.dedent(f"""\
        {entry_begin}
        UID:{md5hash}
        {entry_mid}
        {entry_end}
        """)
        return entry

    warnings = []
    ical_entries = []
    now_str = _encode_datetime(now)

    env = orgparse.OrgEnv(filename=None, todos=todo_states, dones=done_states)
    source = orgparse.loads(org_str, None, env=env)
    for node in source.root[1:]:  # [1:] for skipping root itself
        if _node_is_ignored(node):
            continue
        summary = node.heading
        #if node.priority:  # Restore priority removed by orgparse
        #    summary = f"[{node.priority}] {summary}"
        summary = summary.strip()
        if summary.startswith("[") and "]" in summary:
            summary = summary[summary.index("]") + 1:].strip()
        description = node.body
        if description != "":
            description += "\n\n"
        description += "Org Path: " + _node_full_path(node)
        if SCHEDULED in include_types:
            n_scheduled = node.body.count(SCHEDULED)
            if n_scheduled > 0:
                if node.scheduled:
                    warnings.append(_construct_warning(
                        node, f"Multiple {SCHEDULED} keywords found"))
                else:
                    warnings.append(_construct_warning(
                        node, f"{SCHEDULED} keyword found but no timestamp"))
            if node.scheduled:
                start = _encode_date(node.scheduled.start)
                rrule = _encode_rrule(node.scheduled._repeater)
                ical_entries.append(_construct_vevent(
                    now_str, start, None, summary, description,
                    categories.union({SCHEDULED}), rrule=rrule, is_dayevent=True))
        if DEADLINE in include_types:
            n_deadline = node.body.count(DEADLINE)
            if n_deadline > 0:
                if node.deadline:
                    warnings.append(_construct_warning(
                        node, f"Multiple {DEADLINE} keywords found"))
                else:
                    warnings.append(_construct_warning(
                        node, f"{DEADLINE} keyword found but no timestamp"))
            if node.deadline:
                start = _encode_date(node.deadline.start)
                rrule = _encode_rrule(node.deadline._repeater)
                ical_entries.append(_construct_vevent(
                    now_str, start, None, summary, description,
                    categories.union({DEADLINE}), rrule=rrule, is_dayevent=True))
        if TIMESTAMP in include_types:
            datelist = node.get_timestamps(active=True, point=True)
            for d in datelist:
                start = _encode_date(d.start)
                rrule = _encode_rrule(d._repeater)
                ical_entries.append(_construct_vevent(
                    now_str, start, None, summary, description,
                    categories.union({TIMESTAMP}), rrule=rrule, is_dayevent=True))
            rangelist = node.get_timestamps(active=True, range=True)
            for d in rangelist:
                start = _encode_date(d.start)
                end = _encode_date(d.end, is_range_end=True)
                rrule = _encode_rrule(d._repeater)
                ical_entries.append(_construct_vevent(
                    now_str, start, end, summary, description,
                    categories.union({"TIMESTAMP"}), rrule=rrule))
        if CLOCK in include_types:
            for d in node.clock:
                start = _encode_date(d.start)
                if d.end is None:
                    continue  # Skip clocks that are still running
                end = _encode_date(d.end)
                ical_entries.append(_construct_vevent(
                    now_str, start, end, summary, description,
                    categories.union({CLOCK})))
                assert d._repeater is None
        if BIRTHDAY in include_types:
            if node.properties.get("BIRTHDAY"):
                start = node.properties.get("BIRTHDAY")
                start = datetime.strptime(start, "%Y-%m-%d")
                #start = start.replace(year=now.year)
                rrule = "RRULE:FREQ=YEARLY;INTERVAL=1"
                bage = now.year - start.year
                description = "- Birthyear: {}\n- Age {}: {}\n\n".format(start.year, now.year, bage)
                start = start.strftime("%Y%m%d")
                ical_entries.append(_construct_vevent(
                    now_str, start, None, '{} Birthday'.format(summary), description,
                    categories.union({BIRTHDAY}), rrule=rrule, is_dayevent=True))
        if DIARY in include_types:
            diaries = _node_get_diaries(node)
            for diary in diaries:
                rrule = _encode_diary_to_rrule(diary)
                if not rrule:
                    warnings.append(_construct_warning(
                        node, f"Invalid diary-float"))
                    continue
                start = None #node.properties.get("CREATED")
                start = start.strftime("%Y%m%d") if start else "19700101"
                
                # parse start/end-time from heading if it exists
                stime, etime, summary2 = _parse_diary_time(node.heading)
                if stime:
                    startt = start + "T" + stime + "00"
                    startt = _encode_datetime(datetime.strptime(startt, "%Y%m%dT%H%M%S"))
                else:
                    startt = start
                if etime:
                    endt = start + "T" + etime + "00"
                    endt = _encode_datetime(datetime.strptime(endt, "%Y%m%dT%H%M%S"))
                else:
                    endt = start
                summary = summary2 if summary2 else summary

                entry = _construct_vevent(
                    now_str, startt, endt, summary, description,
                    categories.union({'REGULAR'}), rrule=rrule)
                ical_entries.append(entry)


    ical_entries_str = "".join(ical_entries).strip()
    
    if just_entries:
        return ical_entries_str, warnings
    else:
        ical_str = f"""\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:{prod_id}{mytimezone}
{ical_entries_str}
END:VCALENDAR
"""
    return ical_str, warnings
