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
        mytimezoneid: str = "",
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
DTSTART:19811025T030000
RRULE:FREQ=YEARLY;UNTIL=20361026T010000Z;BYDAY=-1SU;BYMONTH=10
END:STANDARD
END:VTIMEZONE"""

    mytimezoneid = "Europe/Vienna"

    mytimezoneprefix = ";TZID={}".format(mytimezoneid)

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
    
    def _fix_time_format(text: str) -> str:
        # Define a regex pattern to match date and time formats like <YYYY-MM-DD DDD H:MM> or <YYYY-MM-DD DDD H:MM-H:MM>
        pattern = re.compile(r'<(\d{4}-\d{2}-\d{2} \w{3}) (\d{1,2}:\d{2})(-(\d{1,2}:\d{2}))?>')
        
        def replacer(match):
            # Extract the date and time parts from the match
            date_part = match.group(1)
            start_time = match.group(2)
            end_time = match.group(4)
            
            # Ensure leading zero for single-digit hours
            fixed_start = start_time.zfill(5)
            fixed_end = end_time.zfill(5) if end_time else ''
            
            # Reconstruct the formatted time string
            return f'<{date_part} {fixed_start}{"-" + fixed_end if fixed_end else ""}>'
        
        # Substitute all occurrences of the pattern in the input text
        return pattern.sub(replacer, text)

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
                # with time in title (so not in the diary-float sexp)
                d = re.findall(r'<%%\(diary-float\s+.*\)>', line)
                if len(d) == 1:
                    diaries.append(d[0])
                elif len(d) > 1:
                    warnings.append(_construct_warning(
                        node, f"Invalid diary-float in body 1: too many matches"))
                    
                # with inline time (new in org 9.7)
                # <%%(diary-float t 2 2) 19:00>
                # <%%(diary-float t 2 2) 19:00-23:00>
                d = re.findall(r'(<%%\(diary-float\s+.*\)\s+\d?\d:\d\d(-\d?\d:\d\d)?>)', line)
                if len(d) == 1:
                    diaries.append(d[0][0]) # findall returns the captured groups as tuple, and we want the first group
                elif len(d) > 1:
                    warnings.append(_construct_warning(
                        node, f"Invalid diary-float in body 2: too many matches"))

        return diaries

    def _encode_diary_to_rrule(diary: str) -> str:
        # <%%(diary-float t 2 2)>
        m = re.search(r'<%%\(diary-float\s([t\+\-\d]*)\s([\+\-\d]*)\s([\+\-\d]*)\)\s*(\d?\d:\d\d)?(-(\d?\d:\d\d))?>', diary)
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

    def _parse_diary_time(diary: str, node: orgparse.OrgNode) -> Tuple[str, str, str]:
        cleantime = lambda x: x.replace(':', '').replace('-', '') if x else None

        # time in sexp:
        m = re.search(r'<%%\(diary-float\s([t\+\-\d]*)\s([\+\-\d]*)\s([\+\-\d]*)\)\s*(\d?\d:\d\d)?(-(\d?\d:\d\d))?>', diary)
        if m and m.group(4):
            return cleantime(m.group(4)), cleantime(m.group(6)), node.heading.strip()

        # time in title:
        # 19:00-23:00 STG
        m = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2}) (.*)', node.heading)
        if m:
            return cleantime(m.group(1)), cleantime(m.group(2)), m.group(3).strip()
        m = re.search(r'(\d{2}:\d{2})', node.heading)
        if m:
            return cleantime(m.group(1)), None, m.group(3).strip()
        
        return None, None, None # stime, etime, summary2


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
            tzprefix: str = ""
            ) -> str:
        startutc = "DTSTART{};VALUE=DATE:{}".format(tzprefix, startutc) if is_dayevent else "DTSTART{}:{}".format(tzprefix, startutc)
        endutc = "DTEND{}:{}".format(tzprefix, endutc) if endutc else ''
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

    org_str = _fix_time_format(org_str) # fix (active) timestamps without leading zero
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
                is_dayevent = type(d.start) == date
                start = _encode_date(d.start)
                end = _encode_date(d.start + timedelta(hours=1)) if not is_dayevent else None
                rrule = _encode_rrule(d._repeater)
                ical_entries.append(_construct_vevent(
                    now_str, start, end, summary, description,
                    categories.union({TIMESTAMP}), rrule=rrule, is_dayevent=is_dayevent))
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
                start = start.strftime("%Y%m%d") if start else "19850101" # diary-sexp without explicit start date → start at beginning of time
                
                # parse start/end-time from heading if it exists
                stime, etime, summary2 = _parse_diary_time(diary, node)
                if stime:
                    startt = start + "T" + stime + "00"
                    #startt = _encode_datetime(datetime.strptime(startt, "%Y%m%dT%H%M%S"))
                else:
                    startt = start
                if etime:
                    endt = start + "T" + etime + "00"
                    #endt = _encode_datetime(datetime.strptime(endt, "%Y%m%dT%H%M%S"))
                elif stime:
                    # parse start into datetime
                    startts = datetime.strptime(stime, "%H%M")
                    etime = (startts + timedelta(hours=1)).strftime("%H%M")
                    endt = start + "T" + etime + "00"
                else:
                    endt = start
                summary = summary2 if summary2 else summary

                # repeated-dates without specific start-date are a bit annoying, 
                # so we hardcode `mytimezoneprefix`

                entry = _construct_vevent(
                    now_str, startt, endt, summary, description,
                    categories.union({'REGULAR'}), rrule=rrule, tzprefix=mytimezoneprefix)
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
