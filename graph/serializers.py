from rest_framework import serializers
from .models import Concept, Relation

class ConceptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Concept
        fields = ["id", "slug", "label", "description", "metadata", "created_at", "updated_at"]

class RelationSerializer(serializers.ModelSerializer):
    source_slug = serializers.CharField(source="source.slug", read_only=True)
    target_slug = serializers.CharField(source="target.slug", read_only=True)

    class Meta:
        model = Relation
        fields = ["id", "source", "source_slug", "target", "target_slug", "type", "metadata", "created_at", "updated_at"]

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", None))
        target = attrs.get("target", getattr(self.instance, "target", None))
        relation_type = attrs.get("type", getattr(self.instance, "type", None))
        if source == target and relation_type not in {"equivalent_to", "related_to"}:
            raise serializers.ValidationError(
                "Self-relations are only allowed for equivalent_to or related_to."
            )
        return attrs
