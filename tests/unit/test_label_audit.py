from llmbim_drawings.label_audit import boxes, overlap_pairs


def test_overlap_detects_stacked_room_labels():
    svg = """
    <svg>
      <text x="100" y="50" font-size="12" text-anchor="middle">Hot cell tunnel (clear) 7583 SF</text>
      <text x="100" y="50" font-size="12" text-anchor="middle">Robotic spine 1572 SF</text>
    </svg>
    """
    hits = overlap_pairs(boxes(svg))
    assert hits, hits


def test_separated_labels_do_not_overlap():
    svg = """
    <svg>
      <text x="10" y="20" font-size="10">AAAA</text>
      <text x="200" y="20" font-size="10">BBBB</text>
    </svg>
    """
    assert not overlap_pairs(boxes(svg))
