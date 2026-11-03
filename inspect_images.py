from pathlib import Path
import nibabel as nib
import numpy as np
project_dir = Path(__file__).resolve().parent
data_dir = project_dir / "pet-ct-radiomicsdataPETCT0011f3deaf"

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
    print("CT and PET transforms match:",
      np.allclose(ct_image.affine, pet_image.affine,
                  rtol=0, atol=1e-4))

print("Mask and PET transforms match:",
      np.allclose(mask_image.affine, pet_image.affine,
                  rtol=0, atol=1e-4))
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
import matplotlib.pyplot as plt

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
plt.show()
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
plt.show()
fig, ax = plt.subplots(figsize=(7, 4))

ax.hist(lesion_values, bins=30, edgecolor="black")
ax.set_xlabel("SUV")
ax.set_ylabel("Number of voxels")
ax.set_title("PET uptake within the full segmentation mask")

fig.tight_layout()
fig.savefig(project_dir / "pet_suv_histogram.png", dpi=200)
plt.show()
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