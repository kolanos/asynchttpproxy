import datetime
import dateutil.relativedelta

BYTE_SUFFIXES = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


def uptime(start, end):
    """Returns the relative uptime given two timestamps."""
    start = datetime.datetime.fromtimestamp(start)
    end = datetime.datetime.fromtimestamp(end)
    rd = dateutil.relativedelta.relativedelta(end, start)
    return {k: getattr(rd, k) for k in ['years', 'months', 'days', 'hours',
                                        'minutes', 'seconds']}


def human_bytes(n):
    if n == 0:
        return '0B'
    i = 0
    while n >= 1024 and i < len(BYTE_SUFFIXES) - 1:
        n /= 1024
        i += 1
    f = ('%.2f' % n).rstrip('0').rstrip('.')
    return '%s %s' % (f, BYTE_SUFFIXES[i])
