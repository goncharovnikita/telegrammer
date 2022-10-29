import click
import os
from os import listdir, mkdir
from os.path import join, isfile
import re
from enum import Enum
import sys
from PIL import Image
import colorful as cf
from colorthief import ColorThief

file_name_strategy_count = "count"

@click.group()
def main():
    """
    Crop/rename/move images for telegram stickers
    """
    pass

"""Main command"""
@main.command()
@click.argument('target_folder')
@click.argument('dest_folder')
@click.option("--pattern", help="Regex pattern to filter files", default=".+(jpe?g|png)")
@click.option("--filename-strategy", default=file_name_strategy_count, help="Strategy of file renaming")
@click.option("--force", default=False, help="Create dest folder if not exists")
@click.option("--dry-run", default=False, is_flag=True, help="Print desired steps without executing them")
@click.option("--remove-original", default=False, is_flag=True, help="Save original images")
@click.option("--add-borders", default=False, is_flag=True, help="Add borders to image to fit square")
def move_images(target_folder, dest_folder, pattern, filename_strategy, force, dry_run, remove_original, add_borders):
    re.compile(pattern)
    (target_files, dest_files, get_files_err) = get_target_and_dest_files(target_folder, dest_folder, force)
    if get_files_err != None:
        p_error(get_files_err)
        return
    filtered_target_files = filter_files(target_files, pattern)
    p_info(p_info("files to be processed: {}".format(filtered_target_files)))
    ( filtered_dest_files, err ) = filter_dest_files(dest_files, filename_strategy)
    if err != None:
        p_error(err)
        return
    (new_filenames_map, err) = get_new_filenames_map(filtered_target_files, filtered_dest_files, filename_strategy)
    if err != None:
        p_error(err)
        return

    process_filenames_map(new_filenames_map, target_folder, dest_folder, dry_run, remove_original, add_borders)

"""Processors"""
def process_filenames_map(filenames_map, target_folder, dest_folder, dry_run, remove_original, add_borders):
    for orig_fname, new_fname in filenames_map.items():
        (orig_path, dest_path) = ("{}/{}".format(target_folder, orig_fname), "{}/{}".format(dest_folder, new_fname))
        process_image_to_dest(orig_path, dest_path, dry_run, remove_original, add_borders)

def process_image_to_dest(orig_path, dest_path, dry_run = False, remove_original = False, add_borders = False):
    img = Image.open(orig_path)
    transformed_img = transform_image_to_fit(img)
    if add_borders:
        img_dominant_color = get_dominant_image_color(orig_path)
        transformed_img = transform_image_to_square(transformed_img, img_dominant_color)
    new_name = re.compile("(.+)\.(jpe?g|png)").search(dest_path).group(1) + ".png"
    if dry_run:
        p_info("[Dry] dry run for saving {} to {}".format(orig_path, new_name))
    else:
        p_info("saving {} to {}".format(orig_path, new_name))
        transformed_img.save(new_name, "PNG")
        if remove_original == True:
            os.remove(orig_path)

"""Filters"""
def filter_dest_files(target_files, filename_strategy):
    if filename_strategy == file_name_strategy_count:
        return ( sort_files_for_count_strategy(filter_dest_files_for_count_strategy(target_files)), None )
    else:
        return ( None, "[Error] Unsupported strategy: '{}'".format(filename_strategy) )

def filter_files(files, pattern):
    return [f for f in files if re.match(pattern, f)]

def filter_dest_files_for_count_strategy(dest_files):
    count_strategy_regex = "^\d+\.(jpe?g|png)$"
    return filter_files(dest_files, count_strategy_regex)

"""Sorters"""
def sort_files_for_count_strategy(files):
    return sorted(files, key=lambda x: int(re.compile("(\d+)\.(jpe?g|png)").search(x).group(1)))

"""Getters"""
def get_dominant_image_color(img):
    return ColorThief(img).get_color(10)

def get_target_and_dest_files(target_folder, dest_folder, force):
    ( target_files, get_dir_error ) = get_dir_files(target_folder)
    if get_dir_error != None:
        return (None, None, get_dir_error)
    ( dest_files, get_dir_error ) = get_dir_files(dest_folder, force)
    if get_dir_error != None:
        return (None, None, get_dir_error)
    return (target_files, dest_files, None)

def get_next_filename_for_count_strategy(dest_files):
    if len(dest_files) == 0:
        return 1
    else:
        last_file = dest_files[-1]
        search_regex = re.compile( "^(\d+)\.(jpe?g|png)$")
        reg_result = search_regex.search(last_file)
        return int(reg_result.group(1))+ 1

def get_new_filenames_map(target_filenames, dest_filenames, filename_strategy):
    if filename_strategy == file_name_strategy_count:
        return (get_new_filenames_map_for_count_strategy(target_filenames, dest_filenames), None)
    else:
        return (None, "[Error] Unsupported strategy: '{}'".format(filename_strategy))

def get_new_filenames_map_for_count_strategy(target_filenames, dest_filenames):
    result = {}
    next_filename_count = int(get_next_filename_for_count_strategy(dest_filenames))
    for fname in target_filenames:
        suffix = re.compile("^.+\.(jpe?g|png)$").search(fname).group(1)
        result[fname] = "{}.{}".format(next_filename_count, suffix)
        next_filename_count += 1

    return result

def get_dir_files(dest_dir, force = False):
    try:
        return ( [f for f in listdir(dest_dir) if isfile(join(dest_dir, f))], None )
    except FileNotFoundError:
        p_info("dest directory not exists, creating {}".format(dest_dir))
        if force:
            try:
                mkdir(dest_dir)
                return ( [], None )
            except:
                return ( None, "[Error] unexpected error while creating dest directory: {}", sys.exc_info()[0] )
        return ( None, "[Error] No such file or directory: {}".format(dest_dir) )

def get_new_image_dimensions(width, height, max_side):
    scale_aspect = max_side / width if width > height else max_side / height
    p_info("scale aspect is {}".format(scale_aspect))
    new_width = width * scale_aspect
    new_height = height * scale_aspect
    return (int(new_width), int(new_height))

"""Transformers"""
def transform_image_to_fit(img):
    max_side = 512
    (width, height) = img.size
    resize_dimensions = get_new_image_dimensions(width, height, max_side)
    p_info(p_info("[ {} ] old image dimensions: {}, new image dimensions: {}".format(img.filename, img.size, resize_dimensions)))
    return img.resize(resize_dimensions)

def transform_image_to_square(img, dominant_color):
    old_size = img.size
    (old_width, old_height) = old_size
    max_side = 512
    new_size = (512, 512)
    new_img = Image.new("RGB", new_size, dominant_color)
    new_dimensions = (int((new_size[0]-old_size[0])/2),
                          int((new_size[1]-old_size[1])/2))
    new_img.paste(img, new_dimensions)

    return new_img

"""Printers"""
def p_info(msg):
    print("{} {}".format(cf.yellow("[INFO]"), msg))

def p_error(msg):
    print("{} {}".format(cf.red("[ERROR]"), msg))

def p_warn(msg):
    print("{} {}".format(cf.yellow("[WARN]"), msg))

"""Run app"""
main()
