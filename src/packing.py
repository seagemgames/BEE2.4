"""Conditions related to packing."""
from typing import Dict, Set, Iterable

import conditions
import srctools.logger
import vbsp_options
from srctools import VMF, Property, Vec


LOGGER = srctools.logger.get_logger(__name__)
COND_MOD_NAME = 'Packing'

# Filenames we've packed, so we can avoid adding duplicate ents.
_PACKED_FILES = set()  # type: Set[str]

PACKLISTS = {}  # type: Dict[str, Set[str]]]


def parse_packlists(props: Property) -> None:
    """Parse the packlists.cfg file, to load our packing lists."""
    for prop in props.find_children('Packlist'):
        PACKLISTS[prop.name] = {
            file.value
            for file in prop
        }


def pack_list(
    vmf: VMF,
    packlist_name: str,
    file_type: str='generic',
) -> None:
    """Pack the given packing list."""
    try:
        packlist = PACKLISTS[packlist_name.casefold()]
    except KeyError:
        LOGGER.warning('Packlist "{}" does not exist!', packlist_name)
    else:
        pack_files(vmf, *packlist, file_type=file_type)


def pack_files(
    vmf: VMF,
    *files: str,
    file_type: str='generic',
) -> None:
    """Add the given files to the packing list."""

    packlist = set(files) - _PACKED_FILES

    if not files:
        return

    ent = vmf.create_ent(
        classname='comp_pack',
        origin=vbsp_options.get(Vec, 'global_ents_loc'),
    )

    for i, file in enumerate(packlist, start=1):
        ent[file_type + str(i)] = file


@conditions.make_result('Pack')
def res_packlist(vmf: VMF, res: Property):
    """Pack files from a packing list."""
    pack_list(vmf, res.value)
    return conditions.RES_EXHAUSTED


@conditions.make_result('PackFile')
def pack_file_cond(vmf: VMF, res: Property):
    """Adda single file to the map."""
    pack_files(vmf, res.value)
    return conditions.RES_EXHAUSTED


@conditions.make_result('PackRename')
def packlist_cond_rename(vmf: VMF, res: Property):
    """Add a file to the packlist, saved under a new name."""
    # Don't do duplicate checks, these are rare enough that it shouldn't
    # be a problem. Srctools can handle that correctly in all cases.
    vmf.create_ent(
        classname='comp_pack_rename',
        filesrc=res['file'],
        filedest=res['dest'],
        filetype=res['type', 'generic'].casefold(),
    )

    return conditions.RES_EXHAUSTED

