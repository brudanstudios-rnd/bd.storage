GET_REVISIONS_QUERY = '''
query GetRevisions($id: String!, $limit: Int = 10) {
    component_revisions(
        where: {
            component_id: {_eq: $id}
        }, 
        order_by: {id: desc},
        limit: $limit
    ) {
        id
        version
        published
        comment
        created_at
        user_id
    }
}
'''

DELETE_COMPONENT_MUTATION = '''
mutation DeleteComponent($id: String!) {
    delete_component_by_pk(id: $id) {
        id
    }
}
'''

# this query upserts
CREATE_REVISION_MUTATION = '''
mutation CreateRevision($id: String!, $tags: jsonb!, $fields: jsonb!) {
    insert_component_revisions_one(
        object: {
            published: false,
            component: {
                data: {
                    id: $id,
                    tags: $tags,
                    fields: $fields
                },
                on_conflict: {
                    constraint: components_pkey,
                    update_columns: id
                }
            }      
        },
        on_conflict: {
            constraint: component_revisions_component_id_version_key,
            update_columns: component_id
        }
    ) {
        id
        version
        published
        comment
        created_at
        user_id
        user {
            email
        }
    }
}
'''

PUBLISH_REVISION_MUTATION = '''
mutation PublishRevision($revision_id: Int!, $comment: String) {
    update_component_revisions_by_pk(
        _set: {published: true, comment: $comment}, 
        pk_columns: {id: $revision_id }
    ) {
        id
    }
}
'''

ACQUIRE_REVISION_MUTATION = '''
mutation AcquireRevision($revision_id: Int!, $user_id: String!) {
    update_component_revisions_by_pk(
        _set: {user_id: $user_id}, 
        pk_columns: {id: $revision_id}
    ) {
        id
    }
}
'''

DELETE_REVISION_MUTATION = '''
mutation DeleteRevision($id: Int!) {
    delete_component_revisions_by_pk(id: $id) {
        id
    }
}
'''
