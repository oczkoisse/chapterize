import os
import xml.etree.ElementTree as ET
import math
import re

import eyed3
from ffmpy import FFmpeg


class Audiobook:
    """
    Reperesents an Audiobook composed of multiple AudiobookParts
    """
    def __init__(self, dirpath):
        self._dirpath = os.path.abspath(dirpath)
        self._parts = [AudiobookPart(f) for f in self._read_dir(self._dirpath)]

    def __iter__(self):
        return iter(self._parts)

    @staticmethod
    def _read_dir(dirname, ext='mp3'):
        """
        Reads audiobook files from a directory as part files in order
        :param dirname:
        :return:
        """
        ext = '.' + ext
        files = []
        for f in sorted(os.listdir(dirname)):
            if f.endswith(ext) or f.endswith(ext.upper()):
                files.append(os.path.join(dirname, f))
        return files

    @property
    def parts(self):
        return self._parts + []

    def merged_chapters(self):
        chapters = []
        for part in self._parts:
            for chapter in part:
                chapters.append(chapter)

        merged_chapters = []
        for pred, succ in zip(chapters[:-1], chapters[1:]):
            merged_chapters.append(Chapter(pred.title, pred.start_anchor, Anchor.Unknown if succ.start_anchor.is_start_anchor() else succ.start_anchor))
        final_chapter = Chapter(chapters[-1].title, chapters[-1].start_anchor)
        merged_chapters.append(final_chapter)

        return merged_chapters

    def _create_subpath(self, subdir):
        out_path = os.path.join(self._dirpath, subdir)
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        return out_path

    def _sanitize_filename(self, filename):
        filename = str(filename).strip().replace(' ', '_')
        return re.sub(r'(?u)[^-\w.]', '', filename)

    def _split(self, idx, chapter, out_path):
        files = None

        out_path = os.path.join(out_path, self._sanitize_filename("{} ".format(idx) + chapter.title) + '.mp3')

        if chapter.end_anchor is Anchor.Unknown:
            # split till the end
            ff = FFmpeg(
                inputs={chapter.start_anchor.filepath: None},
                outputs={out_path: '-c copy -ss {}'.format(chapter.start_anchor.time)}
            )
            ff.run()
        elif chapter.start_anchor.filepath == chapter.end_anchor.filepath:
            # split from the same file into a single file
            ff = FFmpeg(
                inputs={chapter.start_anchor.filepath: None},
                outputs={out_path: '-c copy -ss {} -to {}'.format(chapter.start_anchor.time, chapter.end_anchor.time)}
            )
            ff.run()
        else:
            # split across more than one file into more than one file
            raise NotImplementedError("Merging of files is not supported yet")
        return files

    def create_chapters(self, out_subdir):
        chapters = self.merged_chapters()
        out_path = self._create_subpath(out_subdir)

        idx = 1
        for chapter in chapters:
            self._split(idx, chapter, out_path)
            idx += 1


class AudiobookPart:
    """
    Represents an Audiobook part file
    """

    def __init__(self, filepath):
        self._filepath = os.path.abspath(filepath)
        self._chapters = self._read_chapters()

    def _read_raw_markers(self):
        audio_file = eyed3.load(self._filepath)
        for user_text_frame in audio_file.tag.user_text_frames:
            if user_text_frame.description.lower().strip() == 'overdrive mediamarkers':
                return user_text_frame.text
        return None

    def _read_chapters(self):
        raw_markers = self._read_raw_markers()
        if raw_markers is None:
            return None
        markers = ET.fromstring(raw_markers)
        chapters = []
        for marker in markers:
            title = marker.find('Name').text.strip()
            start_time = marker.find('Time').text.strip()
            chapters.append(Chapter(title, Anchor(self._filepath, start_time)))
        return chapters

    def __iter__(self):
        return iter(self._chapters)

    @property
    def chapters(self):
        return self._chapters + []

    @property
    def filepath(self):
        return self._filepath

    @property
    def filename(self):
        return os.path.basename(self._filepath)


class Anchor:
    def __init__(self, filepath, time):
        self._filepath = os.path.abspath(filepath) if filepath != '' else ''
        self._time_hh, self._time_mm, self._time_ss = self._split_time(time) if time.strip() != '' else ('', '', '')

    @property
    def filepath(self):
        return self._filepath

    @property
    def time(self):
        return "{}:{}:{}".format(self._time_hh, self._time_mm, self._time_ss)

    @property
    def time_hh(self):
        return self._time_hh

    @property
    def time_mm(self):
        return self._time_mm

    @property
    def time_ss(self):
        return self._time_ss

    def is_start_anchor(self):
        return int(self._time_mm) == 0 and math.isclose(0.000, float(self._time_ss), abs_tol=0.01)

    def _split_time(self, time):
        time_split = time.strip().split(':')
        if len(time_split) == 2:
            mm, ss = time_split
            if int(mm) >= 60:
                hh = str(int(mm) // 60).zfill(2)
                mm = str(int(mm) % 60).zfill(2)
            else:
                hh = '00'

        elif len(time_split) == 3:
            hh, mm, ss = time_split
        else:
            raise Exception("Error while parsing time: {}".format(time))
        return hh, mm, ss

    def __repr__(self):
        if self is Anchor.Unknown:
            return "?"
        return "{}: {}".format(os.path.basename(self._filepath), self._time)


Anchor.Unknown = Anchor('', '')


class Chapter:
    """
    Represents a chapter within an audiobook
    """
    def __init__(self, title, start, end=Anchor.Unknown):
        self._title = title
        assert isinstance(start, Anchor) and isinstance(end, Anchor)
        self._start = start
        self._end = end

    @property
    def start_anchor(self):
        return self._start

    @property
    def end_anchor(self):
        return self._end

    @end_anchor.setter
    def end_anchor(self, val):
        assert isinstance(val, Anchor)
        self._end = val

    @property
    def title(self):
        return self._title

    def is_end_known(self):
        return self._end is not Anchor.Unknown

    def __repr__(self):
        return "{} [{} -> {}]".format(self._title, self._start, self._end)


if __name__ == '__main__':
    ab = Audiobook('/run/media/rahul/My Passport/Audiobooks/George R. R. Martin - A Song of Ice and Fire-Book 1-A Game of Thrones - 1996/')
    ab.create_chapters('merged')