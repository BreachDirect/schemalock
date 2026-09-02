//! schemalock CLI — `schemalock test --config schemalock.yaml --base-url ...`

#![forbid(unsafe_code)]

use clap::{Args, Parser, Subcommand};
use schemalock::config::load_config;
use schemalock::report::{exit_code, render_console, render_json};
use schemalock::runner::Runner;
use std::process::ExitCode;
use std::time::Duration;

#[derive(Parser)]
#[command(name = "schemalock", version)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Run contract checks against a target
    Test(TestArgs),
}

#[derive(Args)]
struct TestArgs {
    /// Path to schemalock.yaml
    #[arg(long)]
    config: String,

    /// Target base URL (overrides config.base_url)
    #[arg(long = "base-url")]
    base_url: Option<String>,

    /// Default auth header, e.g. 'Authorization: Bearer xyz'
    #[arg(long = "auth-header")]
    auth_header: Option<String>,

    /// Write JSON report to this path
    #[arg(long = "json-report")]
    json_report: Option<String>,

    /// Per-request timeout in seconds
    #[arg(long, default_value_t = 10.0)]
    timeout: f64,

    /// Abort a request whose response body exceeds this many bytes (default: 10 MiB)
    #[arg(long = "max-response-bytes")]
    max_response_bytes: Option<usize>,
}

fn main() -> ExitCode {
    let cli = Cli::parse();

    match cli.command {
        Command::Test(args) => run_test(args),
    }
}

fn run_test(args: TestArgs) -> ExitCode {
    let config = match load_config(&args.config) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("SchemaLock config error: {e}");
            return ExitCode::from(2);
        }
    };
    let config_name = config.name.clone();

    let runner = match Runner::new(
        config,
        args.base_url,
        args.auth_header,
        Duration::from_secs_f64(args.timeout),
        args.max_response_bytes,
    ) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("SchemaLock error: {}", e.0);
            return ExitCode::from(2);
        }
    };

    let results = match runner.run() {
        Ok(r) => r,
        Err(e) => {
            eprintln!("SchemaLock error: {}", e.0);
            return ExitCode::from(2);
        }
    };

    println!("{}", render_console(&config_name, &results));

    if let Some(path) = &args.json_report {
        if let Err(e) = render_json(&config_name, &results, path) {
            eprintln!("failed to write JSON report: {e}");
            return ExitCode::from(2);
        }
        println!("\nJSON report written to {path}");
    }

    ExitCode::from(exit_code(&results) as u8)
}
