class Backeer < Formula
  include Language::Python::Virtualenv

  desc "YouTube audio to Audacity stems — downloads, separates with Demucs, opens in Audacity"
  homepage "https://github.com/architgosain/Backeer"
  head "https://github.com/architgosain/Backeer.git", branch: "main"

  depends_on "python@3.13"
  depends_on "yt-dlp"
  depends_on "ffmpeg"

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Backeer needs two Python packages that are not bundled in this formula
      because they pull in PyTorch (~2 GB):

        pip install demucs torchcodec

      Optionally create a backeer.toml in your project root:

        [backeer]
        model = "htdemucs_6s"
        runs-dir = "~/backeer-runs"
        with-audacity = true

      Available models: htdemucs_6s (6 stems), htdemucs (4 stems),
      htdemucs_ft (4 stems, fine-tuned), mdx_extra (4 stems).
    EOS
  end

  test do
    system bin/"backeer", "--help"
  end
end
