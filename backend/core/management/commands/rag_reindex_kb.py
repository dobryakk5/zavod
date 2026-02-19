from __future__ import annotations

from django.core.management.base import BaseCommand

from rag.ingestion import reindex_kb_documents


class Command(BaseCommand):
    help = "Reindex KB documents into RAG chunks (map.kb_chunks)."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, default=None, help="Client(workspace) id")
        parser.add_argument("--document-id", type=int, default=None, help="Single KB document id")
        parser.add_argument("--limit", type=int, default=None, help="Limit number of processed documents")
        parser.add_argument(
            "--include-archived",
            action="store_true",
            help="Include archived KB documents",
        )

    def handle(self, *args, **options):
        stats = reindex_kb_documents(
            workspace_id=options["workspace_id"],
            document_id=options["document_id"],
            include_archived=bool(options["include_archived"]),
            limit=options["limit"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "RAG reindex complete: "
                f"total={stats['total']} indexed={stats['indexed']} "
                f"skipped={stats['skipped']} missing={stats['missing']} "
                f"failed={stats['failed']}"
            )
        )
