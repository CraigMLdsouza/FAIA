from ingestion import parse_args


def test_ingestion_outputs_are_grouped_under_data():
    args = parse_args([])

    assert args.validated_tools_output == "data/validated_tools.json"
    assert args.provider_summary_output == "data/provider_summary.json"
    assert args.repository_summary_output == "data/repository_summary.json"
    assert args.report == "data/ingestion_report.json"
