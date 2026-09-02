//! End-to-end test: reuses the same mock_server.py + escrow_api.yaml fixture
//! that the Python implementation's tests use, so both implementations are
//! validated against one canonical example.

use std::net::TcpStream;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

fn repo_root() -> std::path::PathBuf {
    // rust/ is a subdirectory of the main repo; examples/ lives one level up.
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("rust/ should have a parent directory")
        .to_path_buf()
}

fn free_port() -> u16 {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("bind");
    listener.local_addr().unwrap().port()
}

fn wait_for_port(port: u16, timeout: Duration) {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    panic!("mock server did not start listening on port {port} in time");
}

struct MockServer {
    child: std::process::Child,
    pub port: u16,
}

impl MockServer {
    fn start(break_contract: bool) -> Self {
        let port = free_port();
        let child = Command::new("python3")
            .args([
                "-m",
                "uvicorn",
                "examples.mock_server:app",
                "--port",
                &port.to_string(),
            ])
            .current_dir(repo_root())
            .env(
                "MOCK_BREAK_CONTRACT",
                if break_contract { "1" } else { "0" },
            )
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("failed to spawn mock server (requires python3 + uvicorn/fastapi installed)");

        wait_for_port(port, Duration::from_secs(10));
        MockServer { child, port }
    }
}

impl Drop for MockServer {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn run_schemalock(base_url: &str, extra_args: &[&str]) -> (i32, String) {
    let config_path = repo_root().join("examples").join("escrow_api.yaml");
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_schemalock"));
    cmd.arg("test")
        .arg("--config")
        .arg(config_path)
        .arg("--base-url")
        .arg(base_url)
        .args(extra_args);

    let output = cmd.output().expect("failed to run schemalock binary");
    let mut combined = String::new();
    combined.push_str(&String::from_utf8_lossy(&output.stdout));
    combined.push_str(&String::from_utf8_lossy(&output.stderr));
    (output.status.code().unwrap_or(-1), combined)
}

#[test]
fn passes_against_correct_mock_server() {
    let server = MockServer::start(false);
    let base_url = format!("http://127.0.0.1:{}", server.port);
    let (code, output) = run_schemalock(&base_url, &[]);
    assert_eq!(code, 0, "expected success, got output:\n{output}");
    assert!(output.contains("12 checks: 12 passed"), "{output}");
}

#[test]
fn fails_against_broken_mock_server() {
    let server = MockServer::start(true);
    let base_url = format!("http://127.0.0.1:{}", server.port);
    let (code, output) = run_schemalock(&base_url, &[]);
    assert_eq!(code, 1, "expected failure, got output:\n{output}");
    assert!(output.contains("FAILED"), "{output}");
}

#[test]
fn errors_when_response_exceeds_max_response_bytes() {
    // Every mock response body is larger than 10 bytes, so each request must
    // be reported as an error and the run must fail (exit 1) — mirroring
    // Python's ResponseTooLarge handling (issue #14).
    let server = MockServer::start(false);
    let base_url = format!("http://127.0.0.1:{}", server.port);
    let (code, output) = run_schemalock(&base_url, &["--max-response-bytes", "10"]);
    assert_eq!(
        code, 1,
        "expected failure for oversized responses, got output:\n{output}"
    );
    assert!(output.contains("response exceeded size limit:"), "{output}");
    assert!(
        output.contains(", 10)"),
        "detail should report the cap: {output}"
    );
}

#[test]
fn passes_when_responses_within_max_response_bytes() {
    // Same run with a generous cap: identical to the uncapped baseline.
    let server = MockServer::start(false);
    let base_url = format!("http://127.0.0.1:{}", server.port);
    let (code, output) = run_schemalock(&base_url, &["--max-response-bytes", "10485760"]);
    assert_eq!(code, 0, "expected success, got output:\n{output}");
    assert!(output.contains("12 checks: 12 passed"), "{output}");
}
