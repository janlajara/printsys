from rest_framework import serializers

class SizeSerializer(serializers.Serializer):
    width = serializers.FloatField()
    length = serializers.FloatField()

    def validate(self, data):
        if data['width'] <= 0 or data['length'] <= 0:
            raise serializers.ValidationError("Width and Length must be positive numbers.")
        return data

class CutSheetSerializer(serializers.Serializer):
    cut_size = SizeSerializer()
    sheet_size = SizeSerializer()

    def validate(self, data):
        cut_size_width = data['cut_size']['width']
        cut_size_length = data['cut_size']['length']
        sheet_size_width = data['sheet_size']['width']
        sheet_size_length = data['sheet_size']['length']

        cut_area = cut_size_width * cut_size_length
        sheet_area = sheet_size_width * sheet_size_length
        max_ratio_limit = 0.0002 # Limit the number of sheets processed to avoid performance issues

        if cut_area > sheet_area or max(cut_size_length, cut_size_width) > max(sheet_size_length, sheet_size_width):
            raise serializers.ValidationError({"cut_size": "Cut size must be smaller than sheet size."})
        if cut_area / sheet_area < max_ratio_limit:
            raise serializers.ValidationError({"sheet_size": "Size difference limit exceeded. Try lowering the value of the sheet sizes."})

        return data
