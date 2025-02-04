from presidio_analyzer import RecognizerResult
from presidio_analyzer import AnalyzerEngine
from pypdf import PdfReader
from presidio_analyzer import RecognizerResult


class Line(object):
    def __init__(self, line_no, buffer, start, end):
        self.line_no = line_no
        self.start = start
        self.end = end
        self.buffer = buffer

    @property
    def content(self):
        return self.buffer[self.start : self.end]  # noqa


def line_generator(buffer):
    line_no = 1
    cur = 0
    next = buffer.find("\n")
    while next != -1:
        if next > 0 and buffer[next - 1] == "\r":
            yield Line(line_no, buffer, start=cur, end=next - 1)
        else:
            yield Line(line_no, buffer, start=cur, end=next)
        cur = next + 1
        next = buffer.find("\n", cur)
        line_no += 1

    yield Line(line_no, buffer, start=cur, end=len(buffer))


class PIIProblem(object):
    """Represents a PII problem found by presidio-cli."""

    def __init__(self, line, recognizer_result, line_content):
        assert isinstance(recognizer_result, RecognizerResult)
        self.recognizer_result = recognizer_result.to_dict()
        #: Line on which the problem was found (starting at 1)
        self.line = line
        #: Column on which the problem was found (starting at 1)
        self.column = self.recognizer_result["start"] + 1
        #: Human-readable description of the problem
        self.explanation = self.recognizer_result["analysis_explanation"]
        #: Identifier of the rule that detected the problem
        self.type = self.recognizer_result["entity_type"]
        # Score as a probability determined by the model
        self.score = self.recognizer_result["score"]
        self.line_content = line_content


def _analyze(buffer, conf):
    """Analyze a text source.
    Returns a generator of PIIProblem objects.
    :param buffer: str, string to read from
    :param conf: presidio_cli configuration object
    """
    assert hasattr(
        buffer, "__getitem__"
    ), "_run() argument must be a buffer, not a stream"

    for line in line_generator(buffer):
        if len(line.content) <= 1000000:
            for result in conf.analyzer.analyze(
                text=line.content,
                entities=conf.entities,
                language=conf.language,
                allow_list=conf.allow_list,
                allow_list_match="regex",
                score_threshold=conf.threshold,
            ):
                p = PIIProblem(line.line_no, result, line.content)
                yield p


def analyze_pdf(filename, conf):
    """Analyzes PDF files specifically."""
    analyzer = AnalyzerEngine()
    reader = PdfReader(filename, strict=False)

    for page in reader.pages:
        text_to_analyze = page.extract_text().replace("\n", " ")
        analyzer_results = analyzer.analyze(
            text=text_to_analyze,
            entities=conf.entities,
            language=conf.language,
            allow_list=conf.allow_list,
            allow_list_match="regex",
            score_threshold=conf.threshold,
        )

        for problem in analyzer_results:
            start = problem.start
            end = problem.end

            results = {}
            results["filename"] = filename
            results["line_number"] = problem.start
            results["line_content"] = str(text_to_analyze)[start:end]

            p = PIIProblem(problem.start, problem, str(text_to_analyze)[start:end])
            yield p


def analyze(input, conf, filepath=None):
    """Analyze a text source.
    Returns a generator of PIIProblem objects.
    :param input: buffer, string or stream to read from
    :param conf: presidio_cli configuration object
    :param filepath: string, string with path to file
    """

    if conf.is_file_ignored(filepath):
        return tuple()
    if isinstance(input, (bytes, str)):
        return _analyze(input, conf)
    elif hasattr(input, "read"):  # Python 2's file or Python 3's io.IOBase
        # We need to have everything in memory to parse correctly
        try:
            content = input.read()
        except UnicodeDecodeError:
            pass
        return _analyze(content, conf)
    else:
        raise TypeError("input should be a string or a stream")
