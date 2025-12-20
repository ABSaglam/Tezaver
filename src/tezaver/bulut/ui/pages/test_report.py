"""
Tezaver Bulut - Test Report UI Page
Shows test results from JUnit XML reports.
"""

import streamlit as st
import os
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from tezaver.bulut.ui.contracts.panel_guard import guarded_render

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Test Raporu", lambda: _render_content(ctx))

def parse_junit_xml(xml_path: str) -> dict:
    """Parse JUnit XML and return summary."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Handle both formats: <testsuite> or <testsuites>
        if root.tag == "testsuites":
            testsuites = root.findall("testsuite")
        else:
            testsuites = [root]
        
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        top_failures = []
        
        for ts in testsuites:
            tests = int(ts.get("tests", 0))
            fails = int(ts.get("failures", 0))
            errs = int(ts.get("errors", 0))
            skips = int(ts.get("skipped", 0))
            
            total += tests
            failed += fails
            errors += errs
            skipped += skips
            
            # Collect failure details
            for tc in ts.findall("testcase"):
                failure = tc.find("failure")
                error = tc.find("error")
                if failure is not None or error is not None:
                    msg = ""
                    if failure is not None:
                        msg = failure.get("message", "")[:120]
                    elif error is not None:
                        msg = error.get("message", "")[:120]
                    
                    top_failures.append({
                        "classname": tc.get("classname", ""),
                        "name": tc.get("name", ""),
                        "message": msg
                    })
        
        passed = total - failed - errors - skipped
        
        # Get file mod time
        mtime = os.path.getmtime(xml_path)
        last_updated = datetime.fromtimestamp(mtime).isoformat()
        
        return {
            "available": True,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "last_updated_ts": last_updated,
            "top_failures": top_failures[:10]
        }
    except Exception as e:
        return {
            "available": False,
            "message": f"Error parsing XML: {e}"
        }


def get_test_report() -> dict:
    """Get test report from latest.xml."""
    xml_path = Path("data/bulut_ops/test_reports/latest.xml")
    
    if not xml_path.exists():
        return {
            "available": False,
            "message": "No test report found. Run: pytest src/tezaver/bulut/tests/ --junitxml=data/bulut_ops/test_reports/latest.xml -q"
        }
    
    return parse_junit_xml(str(xml_path))


def _render_content(ctx=None):
    """Render the test report page."""
    
    # st.title("🧪 Test Raporu") # guard sets header? No, it catches.
    st.header("🧪 Test Raporu")
    st.caption("Tezaver Bulut test suite durumu")
    
    # Refresh button
    if st.button("🔄 Yenile"):
        st.rerun()
    
    # Get report
    report = get_test_report()
    
    if not report.get("available"):
        st.warning(report.get("message", "Test raporu mevcut değil."))
        st.markdown("### Test Komutları")
        cmd = "pytest src/tezaver/bulut/tests/ --junitxml=data/bulut_ops/test_reports/latest.xml -q"
        st.code(cmd, language="bash")
        return
    
    # Summary cards
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Toplam", report["total"])
    with col2:
        st.metric("✅ Geçti", report["passed"], delta=None)
    with col3:
        delta_color = "off" if report["failed"] == 0 else "inverse"
        st.metric("❌ Başarısız", report["failed"])
    with col4:
        st.metric("⏭️ Atlandı", report["skipped"])
    with col5:
        st.metric("💥 Hata", report["errors"])
    
    # Status badge
    if report["failed"] == 0 and report["errors"] == 0:
        st.success("🟢 Tüm testler başarılı!")
    else:
        st.error(f"🔴 {report['failed'] + report['errors']} test başarısız")
    
    st.caption(f"Son güncelleme: {report['last_updated_ts']}")
    
    # Top failures
    if report.get("top_failures"):
        st.markdown("### Başarısız Testler")
        for f in report["top_failures"]:
            with st.expander(f"❌ {f['name']}", expanded=False):
                st.text(f"Class: {f['classname']}")
                st.text(f"Hata: {f['message']}")
    
    # Test Commands
    st.markdown("---")
    st.markdown("### Test Komutları")
    
    with st.expander("📋 Kopyalanabilir Komutlar", expanded=True):
        st.code("# Rapor üret\npytest src/tezaver/bulut/tests/ --junitxml=data/bulut_ops/test_reports/latest.xml -q", language="bash")
        st.code("# Hızlı çalıştır\npytest src/tezaver/bulut/tests/ -q", language="bash")
        st.code("# İlk hata'da dur\npytest src/tezaver/bulut/tests/ -q --maxfail=1", language="bash")


# For standalone usage
if __name__ == "__main__":
    render_page()

# Alias
render_test_report_page = render_page
