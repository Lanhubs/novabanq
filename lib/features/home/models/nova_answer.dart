class NovaAnswer {
  const NovaAnswer({required this.kind, required this.answer, this.data});

  final String kind;
  final String answer;
  final Map<String, dynamic>? data;

  factory NovaAnswer.fromJson(Map<String, dynamic> json) => NovaAnswer(
    kind: json['kind'] as String,
    answer: json['answer'] as String,
    data: json['data'] as Map<String, dynamic>?,
  );
}
