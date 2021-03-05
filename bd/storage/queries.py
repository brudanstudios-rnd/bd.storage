CREATE_COMPONENT_MUTATION = '''
mutation CreateComponent($id: String!, $tags: jsonb!, $fields: jsonb!, $metadata: jsonb) {
    createComponent(
        object: {
            id: $id, 
            tags: $tags, 
            fields: $fields, 
            metadata: $metadata,
            revisions: {
                data: {
                    published: false
                }
            }
        }
    ){
        id
        tags
        fields
        metadata
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
'''

CREATE_REVISION_MUTATION = '''
mutation CreateRevision($component_id: String!) {
    createComponentRevision(object: {component_id: $component_id}){
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
'''

PUBLISH_REVISION_MUTATION = '''
mutation ChangeRevisionStatus($revision_id: Int!, $comment: String) {
    updateComponentRevision(_set: {published: true, comment: $comment}, pk_columns: {id: $revision_id}) {
        id
    }
}
'''

CHANGE_REVISION_OWNERSHIP_MUTATION = '''
mutation ChangeRevisionOwnership($revision_id: Int!, $user_id: String) {
    updateComponentRevision(_set: {user_id: $user_id}, pk_columns: {id: $revision_id}) {
        id
    }
}
'''

UPDATE_COMPONENT_META_MUTATION = '''
mutation UpdateComponentMetadata($id: String!, $metadata: jsonb!) {
    updateComponent(_set: {metadata: $metadata}, pk_columns: {id: $id}) {
        id
    }
}
'''

FIND_COMPONENT_QUERY = '''
query FindComponent(
    $id: String!, 
    $num_revisions: Int, 
    $max_revision_version: Int
) {
    getComponent(id: $id) {
        id
        tags
        fields
        metadata
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
'''

FIND_COMPONENTS_QUERY = '''
query FindComponents($id_list: [String!]!, $num_revisions: Int) {
    getComponents(where: {id: {_in: $id_list}}) {
        id
        tags
        fields
        metadata
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
'''
