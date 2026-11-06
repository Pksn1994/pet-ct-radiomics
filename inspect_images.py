"""Inspect one PET/CT study and explore changes to its segmentation mask."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Save figures without opening plot windows in WSL.
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import nibabel as nib
import numpy as np
from scipy import ndimage

def load_images(data_dir):
    print("Data folder:", data_dir)
    print("Folder exists:", data_dir.is_dir())
    pet_path = data_dir / "SUV.nii.gz"
    pet_image = nib.load(pet_path)

    print("PET dimensions:", pet_image.shape)
    print("PET voxel sizes:", pet_image.header.get_zooms()[:3])
    print("Spatial units:", pet_image.header.get_xyzt_units()[0])
    ct_image = nib.load(data_dir / "CTres.nii.gz")
    mask_image = nib.load(data_dir / "SEG.nii.gz")

    for name, image in [("CT", ct_image), ("Mask", mask_image)]:
        print(name, "dimensions:", image.shape)
        print(name, "voxel sizes:", image.header.get_zooms()[:3])
        print(name, "spatial units:", image.header.get_xyzt_units()[0])


    print("Mask and PET transforms match:",
          np.allclose(mask_image.affine, pet_image.affine,
                      rtol=0, atol=1e-4))
    print("CT and PET transforms match:",
          np.allclose(ct_image.affine, pet_image.affine, rtol=0, atol=1e-4))

    return pet_image, ct_image, mask_image


def save_mask_statistics(pet_image, mask_image, project_dir):
    mask_data = np.asarray(mask_image.dataobj)
    print("Mask labels:", np.unique(mask_data))
    print("Nonzero mask voxels:", np.count_nonzero(mask_data))
    pet_data = pet_image.get_fdata(dtype=np.float32)
    lesion_values = pet_data[mask_data == 1]

    print("Selected PET voxels:", lesion_values.size)
    print("All selected values finite:", np.isfinite(lesion_values).all())
    print("Mean SUV within mask:", np.mean(lesion_values))
    print("Median SUV within mask:", np.median(lesion_values))
    print("Maximum SUV within mask:", np.max(lesion_values))
    print("SUV standard deviation:", np.std(lesion_values))
    results = [[
        lesion_values.size,
        np.mean(lesion_values),
        np.median(lesion_values),
        np.max(lesion_values),
        np.std(lesion_values)
    ]]

    np.savetxt(
        project_dir / "pet_mask_statistics.csv",
        results,
        delimiter=",",
        header="voxel_count,mean_suv,median_suv,max_suv,std_suv",
        comments="",
        fmt=["%d", "%.6f", "%.6f", "%.6f", "%.6f"]
    )
    lesion_voxels_per_slice = np.count_nonzero(mask_data == 1, axis=(0, 1))
    slice_index = int(np.argmax(lesion_voxels_per_slice))

    print("Slice index with most lesion voxels:", slice_index)
    print("Lesion voxels in this slice:", lesion_voxels_per_slice[slice_index])
    # Find every slice containing labelled voxels
    mask_slices = np.flatnonzero(lesion_voxels_per_slice > 0)

    print("Slices containing the mask:", mask_slices)
    print("Number of slices containing the mask:", mask_slices.size)

    return pet_data, mask_data, lesion_values, mask_slices, slice_index


def make_slice_figures(pet_image, ct_image, mask_data, lesion_values, slice_index, project_dir):
    pet_slice = np.asarray(pet_image.dataobj[:, :, slice_index])
    mask_slice = mask_data[:, :, slice_index]

    fig, ax = plt.subplots(figsize=(7, 7))

    pet_display = ax.imshow(
        pet_slice.T, cmap="gray_r", origin="lower",
        vmin=0, vmax=10
    )

    ax.contour(
        mask_slice.T, levels=[0.5],
        colors="red", linewidths=1
    )

    ax.set_title(f"PET with lesion outline | slice {slice_index}")
    fig.colorbar(pet_display, ax=ax, label="SUV")
    plt.close(fig)
    ct_slice = np.asarray(ct_image.dataobj[:, :, slice_index])

    fig, ax = plt.subplots(figsize=(7, 7))

    ct_display = ax.imshow(
        ct_slice.T, cmap="gray", origin="lower",
        vmin=-150, vmax=250
    )

    ax.contour(
        mask_slice.T, levels=[0.5],
        colors="red", linewidths=1
    )

    ax.set_title(f"CT with lesion outline | slice {slice_index}")
    fig.colorbar(ct_display, ax=ax, label="CT intensity")
    fig.savefig(project_dir / "ct_mask_slice296.png",
                dpi=200, bbox_inches="tight")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))

    ax.hist(lesion_values, bins=30, edgecolor="black")
    ax.set_xlabel("SUV")
    ax.set_ylabel("Number of voxels")
    ax.set_title("PET uptake within the full segmentation mask")

    fig.tight_layout()
    fig.savefig(project_dir / "pet_suv_histogram.png", dpi=200)
    plt.close(fig)


def make_slice_overviews(pet_data, ct_image, mask_data, mask_slices, project_dir):
    lesion_voxels_per_slice = np.count_nonzero(mask_data == 1, axis=(0, 1))
    # View all slices containing the mask
    fig, axes = plt.subplots(4, 6, figsize=(18, 12))

    for ax, z in zip(axes.flat, mask_slices):
        ct_slice = np.asarray(ct_image.dataobj[:, :, z])
        mask_slice = mask_data[:, :, z]

        ax.imshow(
            ct_slice.T, cmap="gray", origin="lower",
            vmin=-150, vmax=250
        )
        ax.contour(
            mask_slice.T, levels=[0.5],
            colors="red", linewidths=0.8
        )
        ax.set_title(f"Slice {z}")
        ax.axis("off")

    for ax in axes.flat[mask_slices.size:]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(project_dir / "ct_mask_all_slices.png", dpi=200)
    plt.close(fig)
    # View PET uptake on all slices containing the mask
    fig, axes = plt.subplots(4, 6, figsize=(18, 12))

    for ax, z in zip(axes.flat, mask_slices):
        ax.imshow(
            pet_data[:, :, z].T,
            cmap="gray_r", origin="lower", vmin=0, vmax=10
        )
        ax.contour(
            mask_data[:, :, z].T,
            levels=[0.5], colors="red", linewidths=0.8
        )
        ax.set_title(f"Slice {z}")
        ax.axis("off")

    for ax in axes.flat[mask_slices.size:]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(project_dir / "pet_mask_all_slices.png", dpi=200)
    plt.close(fig)
    # Save the mask voxel count for each labelled slice
    slice_counts = np.column_stack((
        mask_slices,
        lesion_voxels_per_slice[mask_slices]
    ))

    np.savetxt(
        project_dir / "mask_voxels_per_slice.csv",
        slice_counts,
        delimiter=",",
        header="slice_index,voxel_count",
        comments="",
        fmt="%d"
    )

    print("Saved mask_voxels_per_slice.csv")


def find_regions(pet_data, mask_data, project_dir):
    # Find connected regions in the 3D mask

    connectivity = ndimage.generate_binary_structure(3, 3)

    region_labels, region_count = ndimage.label(
        mask_data == 1,
        structure=connectivity
    )

    print("Connected regions in the mask:", region_count)
    # Count voxels in each connected region
    region_sizes = np.bincount(region_labels.ravel())[1:]

    for region_id, voxel_count in enumerate(region_sizes, start=1):
        print(f"Region {region_id}: {voxel_count} voxels")

    print("Total voxels across regions:", region_sizes.sum())
    # Calculate PET statistics for each connected region
    region_results = []

    for region_id in range(1, region_count + 1):
        values = pet_data[region_labels == region_id]

        region_results.append([
            region_id,
            values.size,
            np.mean(values),
            np.median(values),
            np.max(values),
            np.std(values)
        ])

    np.savetxt(
        project_dir / "pet_region_statistics.csv",
        region_results,
        delimiter=",",
        header="region_id,voxel_count,mean_suv,median_suv,max_suv,std_suv",
        comments="",
        fmt=["%d", "%d", "%.6f", "%.6f", "%.6f", "%.6f"]
    )

    print("Saved pet_region_statistics.csv")

    return region_labels, region_count


def make_region_views(pet_image, ct_image, mask_data, region_labels, region_count, project_dir):
    # Create closer PET and CT views of each connected region
    region_boxes = ndimage.find_objects(region_labels)
    fig, axes = plt.subplots(
        region_count, 2,
        figsize=(10, 4 * region_count),
        squeeze=False
    )

    for region_id, box in enumerate(region_boxes, start=1):
        x_box, y_box, z_box = box
        local_labels = region_labels[box]

        counts = np.count_nonzero(local_labels == region_id, axis=(0, 1))
        z = z_box.start + int(np.argmax(counts))

        # Add some surrounding anatomy to the crop
        margin = 15
        x0 = max(0, x_box.start - margin)
        x1 = min(mask_data.shape[0], x_box.stop + margin)
        y0 = max(0, y_box.start - margin)
        y1 = min(mask_data.shape[1], y_box.stop + margin)

        outline = region_labels[x0:x1, y0:y1, z] == region_id

        for col, (image, cmap, low, high, name) in enumerate([
            (pet_image, "gray_r", 0, 10, "PET"),
            (ct_image, "gray", -150, 250, "CT")
        ]):
            ax = axes[region_id - 1, col]
            crop = np.asarray(image.dataobj[x0:x1, y0:y1, z])

            ax.imshow(
                crop.T, cmap=cmap, origin="lower",
                vmin=low, vmax=high
            )
            ax.contour(
                outline.T, levels=[0.5],
                colors="red", linewidths=1
            )
            ax.set_title(f"Region {region_id} | {name} | slice {z}")
            ax.axis("off")

    fig.tight_layout()
    fig.savefig(
        project_dir / "pet_ct_regions.png",
        dpi=200, bbox_inches="tight"
    )
    plt.close(fig)

    print("Saved pet_ct_regions.png")

    # Save the slice range and displayed slice for each region
    region_locations = []

    for region_id, box in enumerate(region_boxes, start=1):
        local_labels = region_labels[box]
        counts = np.count_nonzero(local_labels == region_id, axis=(0, 1))

        first_slice = box[2].start
        last_slice = box[2].stop - 1
        selected_slice = first_slice + int(np.argmax(counts))

        region_locations.append([
            region_id, first_slice, last_slice, selected_slice
        ])

    np.savetxt(
        project_dir / "region_locations.csv",
        region_locations,
        delimiter=",",
        header="region_id,first_slice,last_slice,selected_slice",
        comments="",
        fmt="%d"
    )

    print("Saved region_locations.csv")

    return region_boxes


def test_region5_mask(pet_data, region_labels, region_boxes, project_dir):
    # Compare Region 5 with slightly smaller and larger masks
    original_mask = region_labels == 5

    # Use face-sharing neighbours for this experiment
    structure = ndimage.generate_binary_structure(3, 1)

    smaller_mask = ndimage.binary_erosion(
        original_mask, structure=structure, iterations=1
    )
    larger_mask = ndimage.binary_dilation(
        original_mask, structure=structure, iterations=1
    )

    for name, region_mask in [
        ("Smaller", smaller_mask),
        ("Original", original_mask),
        ("Larger", larger_mask)
    ]:
        values = pet_data[region_mask]

        if values.size == 0:
            print(f"{name}: mask is empty")
        else:
            print(
                f"{name}: {values.size} voxels, "
                f"mean SUV = {np.mean(values):.6f}"
            )

    # Save the mask-change experiment
    original_mean = float(np.mean(pet_data[original_mask]))
    sensitivity_results = []

    for name, region_mask in [
        ("smaller", smaller_mask),
        ("original", original_mask),
        ("larger", larger_mask)
    ]:
        values = pet_data[region_mask]
        mean_suv = float(np.mean(values)) if values.size else np.nan
        change_pct = 100 * (mean_suv - original_mean) / original_mean

        sensitivity_results.append([
            5, name, values.size, mean_suv, change_pct
        ])


    with open(
        project_dir / "region5_mask_sensitivity.csv",
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "region_id", "mask", "voxel_count",
            "mean_suv", "mean_suv_change_pct"
        ])
        writer.writerows(sensitivity_results)

    print("Saved region5_mask_sensitivity.csv")
    # Show the mask changes on one PET slice

    box = region_boxes[4]  # Region 5
    z = 298
    margin = 15

    x0 = max(0, box[0].start - margin)
    x1 = min(pet_data.shape[0], box[0].stop + margin)
    y0 = max(0, box[1].start - margin)
    y1 = min(pet_data.shape[1], box[1].stop + margin)

    fig, ax = plt.subplots(figsize=(7, 6))

    display = ax.imshow(
        pet_data[x0:x1, y0:y1, z].T,
        cmap="gray_r", origin="lower",
        vmin=0, vmax=10,
        interpolation="nearest"
    )

    legend_handles = []

    for name, region_mask, color in [
        ("Smaller", smaller_mask, "blue"),
        ("Original", original_mask, "red"),
        ("Larger", larger_mask, "green")
    ]:
        outline = region_mask[x0:x1, y0:y1, z]

        ax.contour(
            outline.T, levels=[0.5],
            colors=[color], linewidths=1.2
        )
        legend_handles.append(
            Line2D([0], [0], color=color, label=name)
        )

    ax.legend(handles=legend_handles, loc="upper right")
    ax.set_title(f"Region 5: mask changes | slice {z}")
    ax.axis("off")
    fig.colorbar(display, ax=ax, label="SUV")
    fig.tight_layout()

    fig.savefig(
        project_dir / "region5_mask_changes.png",
        dpi=200, bbox_inches="tight"
    )
    plt.close(fig)

    print("Saved region5_mask_changes.png")


def test_all_region_masks(pet_data, region_labels, region_count, project_dir):
    # Test mask changes for all connected regions
    all_results = []
    structure = ndimage.generate_binary_structure(3, 1)

    for region_id in range(1, region_count + 1):
        region_mask = region_labels == region_id
        baseline_mean = float(np.mean(pet_data[region_mask]))

        masks = [
            ("smaller", ndimage.binary_erosion(
                region_mask, structure=structure, iterations=1
            )),
            ("original", region_mask),
            ("larger", ndimage.binary_dilation(
                region_mask, structure=structure, iterations=1
            ))
        ]

        for name, changed_mask in masks:
            values = pet_data[changed_mask]

            if values.size == 0:
                mean_suv = np.nan
                change_pct = np.nan
            else:
                mean_suv = float(np.mean(values))
                change_pct = (
                    100 * (mean_suv - baseline_mean) / baseline_mean
                )

            all_results.append([
                region_id, name, values.size, mean_suv, change_pct
            ])

    with open(
        project_dir / "all_regions_mask_sensitivity.csv",
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "region_id", "mask", "voxel_count",
            "mean_suv", "mean_suv_change_pct"
        ])
        writer.writerows(all_results)

    print("Saved all_regions_mask_sensitivity.csv")


def save_ct_statistics(ct_image, region_labels, region_count, project_dir):
    # Calculate CT intensity statistics for each connected region
    ct_data = ct_image.get_fdata(dtype=np.float32)
    ct_results = []

    for region_id in range(1, region_count + 1):
        values = ct_data[region_labels == region_id]

        ct_results.append([
            region_id,
            values.size,
            float(np.mean(values)),
            float(np.median(values)),
            float(np.min(values)),
            float(np.max(values)),
            float(np.std(values))
        ])

    with open(
        project_dir / "ct_region_statistics.csv",
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "region_id", "voxel_count", "mean_ct", "median_ct",
            "min_ct", "max_ct", "std_ct"
        ])
        writer.writerows(ct_results)

    print("Saved ct_region_statistics.csv")


def main():
    project_dir = Path(__file__).resolve().parent
    data_dir = project_dir / "pet-ct-radiomicsdataPETCT0011f3deaf"

    pet_image, ct_image, mask_image = load_images(data_dir)
    pet_data, mask_data, lesion_values, mask_slices, slice_index = save_mask_statistics(
        pet_image, mask_image, project_dir
    )
    make_slice_figures(
        pet_image, ct_image, mask_data, lesion_values, slice_index, project_dir
    )
    make_slice_overviews(pet_data, ct_image, mask_data, mask_slices, project_dir)

    region_labels, region_count = find_regions(pet_data, mask_data, project_dir)
    region_boxes = make_region_views(
        pet_image, ct_image, mask_data, region_labels, region_count, project_dir
    )

    # This example uses Region 5 and slice 298 from the current study.
    test_region5_mask(pet_data, region_labels, region_boxes, project_dir)
    test_all_region_masks(pet_data, region_labels, region_count, project_dir)
    save_ct_statistics(ct_image, region_labels, region_count, project_dir)


if __name__ == "__main__":
    main()
