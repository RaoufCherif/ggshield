from requests.utils import DEFAULT_CA_BUNDLE_PATH, extract_zipped_paths
_PATCH_WITH_NONEWLINE_BEFORE_SECRET = """
diff --git a/artifactory b/artifactory
index 2ace9c7..4c7699d 100644
--- a/artifactory
+++ b/artifactory
@@ -1,3 +1,3 @@
 some line
 some other line
-deleted line
\\ No newline at end of file
+sg_key = "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"
\\ No newline at end of file
"""



@pytest.fixture(scope="function")
def isolated_fs(fs):
    # isolate fs but include CA bundle for https validation
    fs.add_real_directory(os.path.dirname(extract_zipped_paths(DEFAULT_CA_BUNDLE_PATH)))
    # add cassettes dir
    cassettes_dir = join(dirname(realpath(__file__)), "cassettes")
    fs.add_real_directory(cassettes_dir)