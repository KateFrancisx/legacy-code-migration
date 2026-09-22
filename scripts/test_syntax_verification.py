import json
from pathlib import Path

from pipeline.verification.syntax_verifier import SyntaxVerifier


def main():
    project_root = Path(__file__).resolve().parents[1]

    migrated_dir = (
        project_root
        / "outputs"
        / "python2_migration_test_repo_migrated"
    )

    output_file = (
        project_root
        / "outputs"
        / "python2_migration_test_repo_syntax_verification.json"
    )

    verifier = SyntaxVerifier()

    result = verifier.verify_directory(migrated_dir)

    print("=" * 70)
    print("CODEMIGRATE - SYNTAX VERIFICATION")
    print("=" * 70)

    print(f"Directory      : {result['directory']}")
    print(f"Files checked  : {result['files_checked']}")
    print(f"Valid files    : {result['valid_files']}")
    print(f"Invalid files  : {result['invalid_files']}")
    print(f"Overall status : {result['overall_status']}")

    print("\nFile Results")
    print("-" * 70)

    for item in result["results"]:
        status = "PASS" if item["syntax_valid"] else "FAIL"

        print(f"{status:6} | {item['file']}")

        if item["error"]:
            print(
                f"       Error: {item['error']} "
                f"(line {item['line']}, column {item['column']})"
            )

    # Save verification results
    output_file.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print("\n[SAVED]")
    print(output_file)


if __name__ == "__main__":
    main()