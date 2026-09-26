class OnboardingDetail {
  final String title;
  final String description;
  final String imagePath;
  const OnboardingDetail({
    required this.title,
    required this.description,
    required this.imagePath,
  });
  factory OnboardingDetail.fromJson(Map<dynamic, String> json) {
    return OnboardingDetail(
      description: json["description"] ?? "",
      title: json["title"] ?? "",
      imagePath: json["imagePath"] ?? "",
    );
  }
}
