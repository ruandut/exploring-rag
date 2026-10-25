"""Read-side queries for the library. Everything is scoped to the requesting user."""

from django.db.models import Count, QuerySet

from .models import Document, Folder


def folders_for(user) -> QuerySet[Folder]:
    return Folder.objects.filter(owner=user).annotate(document_count=Count("documents"))


def get_folder(user, folder_id: int) -> Folder:
    return Folder.objects.get(owner=user, pk=folder_id)


def documents_for(user, *, folder: str | None = None) -> QuerySet[Document]:
    """folder: None/"all" = everything, "root" = top level only, otherwise a folder id."""
    qs = Document.objects.filter(owner=user)
    if folder == "root":
        return qs.filter(folder__isnull=True)
    if folder not in (None, "", "all"):
        return qs.filter(folder_id=int(folder))
    return qs


def get_document(user, document_id: int) -> Document:
    return Document.objects.get(owner=user, pk=document_id)


def get_document_for_indexing(document_id: int) -> Document | None:
    """Used by rag's worker task, which runs outside any request (no user to scope by)."""
    return Document.objects.select_related("owner").filter(pk=document_id).first()


def document_ids_for(user_id: int) -> list[int]:
    return list(Document.objects.filter(owner_id=user_id).values_list("pk", flat=True))


def folder_subtree_ids(user, folder_ids: list[int]) -> list[int]:
    """The given folders plus every folder nested under them (only the user's own)."""
    found = set(Folder.objects.filter(owner=user, pk__in=folder_ids).values_list("pk", flat=True))
    frontier = set(found)
    while frontier:
        frontier = (
            set(
                Folder.objects.filter(owner=user, parent_id__in=frontier).values_list(
                    "pk", flat=True
                )
            )
            - found
        )
        found |= frontier
    return sorted(found)


def document_ids_in_folders(user, folder_ids: list[int]) -> list[int]:
    return list(
        Document.objects.filter(
            owner=user, folder_id__in=folder_subtree_ids(user, folder_ids)
        ).values_list("pk", flat=True)
    )
