"""The shareable report retains data and cannot inject script markup."""
import json
from pathlib import Path
import tempfile
import unittest
import feedguard
import replay

class ReplayTests(unittest.TestCase):
    def test_export_keeps_classifications_and_escapes_script_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=Path(directory)/'trace.json'; output=Path(directory)/'report.html'
            rows=feedguard.demo()
            rows[0]['note']='</script><script>alert(1)</script>'
            trace.write_text(json.dumps(rows))
            replay.export(trace,output)
            page=output.read_text()
            self.assertIn('FeedGuard',page)
            self.assertIn('PYTHON REFERENCE',page)
            self.assertNotIn(rows[0]['note'],page)
            self.assertIn('overlap',page)
            self.assertIn('reset_required',page)

    def test_empty_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=Path(directory)/'trace.json'; trace.write_text('[]')
            with self.assertRaises(ValueError):
                replay.export(trace,Path(directory)/'out.html')

if __name__=='__main__': unittest.main()
