CREATE_COMPONENT_MUTATION = '''
mutation CreateComponent($id: String!, $tags: jsonb!, $fields: jsonb!, $metadata: jsonb) {
    createComponents(
        objects: {
            id: $id, 
            tags: $tags, 
            fields: $fields, 
            metadata: $metadata, 
            releases: {
                data: {
                    published: false, 
                    revisions: {
                        data: {
                            published: false
                        }
                    }
                }
            }
        }
    ){
        affected_rows
        returning {
            id
            tags
            fields
            metadata
            releases {
                id
                version
                published
                revisions {
                    id
                    version
                    comment
                    published
                    user {
                        id
                        email
                    }
                }
            }
        }
    }
}
'''

CREATE_RELEASE_MUTATION = '''
mutation CreateComponentRelease($component_id: String!) {
    createComponentReleases(objects: {component_id: $component_id, revisions: {data: {published: false}}}){
        returning {
            id
            version
            published
            revisions {
                id
                version
                comment
                published
                user {
                    id
                    email
                }
            }
        }
    }
}
'''

PUBLISH_RELEASE_MUTATION = '''
mutation PublishRelease($release_id: Int!, $revision_id: Int!, $comment: String) {
    updateComponentReleases(_set: {published: true}, where: {id: {_eq: $release_id}}) {
        affected_rows
    }
    updateComponentRevisions(_set: {published: true, comment: $comment}, where: {id: {_eq: $revision_id}}) {
        affected_rows
    }
}
'''

CREATE_REVISION_MUTATION = '''
mutation CreateRevision($release_id: Int!) {
    createComponentRevisions(objects: {release_id: $release_id}){
        returning {
            id
            version
            comment
            published
            user {
                id
                email
            }
        }
    }
}
'''

CHANGE_REVISION_STATUS_MUTATION = '''
mutation ChangeRevisionStatus($revision_id: Int!, $comment: String) {
    updateComponentRevisions(_set: {published: true, comment: $comment}, where: {id: {_eq: $revision_id}}) {
        affected_rows
    }
}
'''

CHANGE_REVISION_OWNERSHIP_MUTATION = '''
mutation ChangeRevisionOwnership($revision_id: Int!, $user_id: String) {
    updateComponentRevisions(_set: {user_id: $user_id}, where: {id: {_eq: $revision_id}}) {
        affected_rows
    }
}
'''

UPDATE_COMPONENT_META_MUTATION = '''
mutation UpdateComponentMetadata($id: String!, $metadata: jsonb!) {
    updateComponents(_set: {metadata: $metadata}, where: {id: {_eq: $id}}) {
        affected_rows
    }
}
'''

FIND_COMPONENT_QUERY = '''
query FindComponent(
    $id: String!, 
    $num_releases: Int, 
    $num_revisions: Int, 
    $max_release_version: Int, 
    $max_revision_version: Int
) {
    getComponent(id: $id) {
        id
        tags
        fields
        metadata
        releases (
            order_by: {id: desc}, 
            limit: $num_releases, 
            where: {
                version: {_lte: $max_release_version}
            }
        ) {
            id
            version
            published
            revisions (
                order_by: {id: desc}, 
                limit: $num_revisions,
                where: {
                    version: {_lte: $max_revision_version}
                }
            ) {
                id
                version
                comment
                published
                user {
                    id
                    email
                }
            }
        }
    }
}
'''

FIND_COMPONENTS_QUERY = '''
query FindComponents($id_list: [String!]!, $num_releases: Int, $num_revisions: Int) {
    getComponents(where: {id: {_in: $id_list}}) {
        id
        tags
        fields
        metadata
        releases (order_by: {id: desc}, limit: $num_releases) {
            id
            version
            published
            revisions (order_by: {id: desc}, limit: $num_revisions) {
                id
                version
                comment
                published
                user {
                    id
                    email
                }
            }
        }
    }
}
'''
