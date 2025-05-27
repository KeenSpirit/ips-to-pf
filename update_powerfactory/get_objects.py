
def all_relevant_objects(app, folders, type_of_obj, objects=None):
    """When performing a GetContents on objects outside your own user, the function
    can take a significant amount of time. This is a quick function to perform
    a similar type function."""
    for folder in folders:
        if not objects:
            objects = folder.GetContents(type_of_obj, 0)
        else:
            objects += folder.GetContents(type_of_obj, 0)
        sub_folders = folder.GetContents("*.IntFolder", 0)
        sub_folders += folder.GetContents("*.IntPrjfolder", 0)
        if sub_folders:
            objects = all_relevant_objects(app, sub_folders, type_of_obj, objects)
    return objects