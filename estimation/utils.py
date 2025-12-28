from rectpack import newPacker
from rectpack.guillotine import GuillotineBafMaxas


def pack_rects(large_size, small_size, rotation=True):
    large_width, large_height = map(float, large_size)
    small_width, small_height = map(float, small_size)

    # Create a new packer instance with GuillotineBafMaxas algorithm
    packer = newPacker(rotation=rotation, pack_algo=GuillotineBafMaxas)  # Allow rotation for better fitting

    # Add the large paper as the single bin (container)
    packer.add_bin(large_width, large_height)

    # Estimate a reasonable number of small papers based on area
    max_possible = int((large_width * large_height) / (small_width * small_height))

    # Add all estimated rectangles at once
    for _ in range(max_possible):
        packer.add_rect(small_width, small_height)

    # Perform the packing only once
    packer.pack()

    # Extract results
    packed_rects = packer.rect_list()
    packed_count = len(packed_rects)

    return packed_count, packed_rects


def estimate_cuts(layout):
    horizontal_cuts = set()
    vertical_cuts = set()

    for rect in layout:
        x_end = rect["x"] + rect["width"]
        y_end = rect["y"] + rect["length"]

        # Add cut positions
        horizontal_cuts.add(rect["y"])
        horizontal_cuts.add(y_end)
        vertical_cuts.add(rect["x"])
        vertical_cuts.add(x_end)

    # Total cuts required
    num_horizontal_cuts = len(horizontal_cuts) - 1
    num_vertical_cuts = len(vertical_cuts) - 1

    return {"x": num_horizontal_cuts, "y": num_vertical_cuts, "total": num_horizontal_cuts + num_vertical_cuts}