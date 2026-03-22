import discord
import argparse
import asyncio
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go

CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:(\w+):(\d+)>")
RATE_LIMIT_DELAY = 1.0  # チャンネル間のスリープ(秒)


@dataclass
class EmojiStat:
    """1つの絵文字に関する詳細統計。"""
    msg_count: int = 0
    reaction_count: int = 0
    is_custom: bool = True
    channels: set = field(default_factory=set)
    per_channel_count: dict = field(default_factory=lambda: defaultdict(int))

    @property
    def total_count(self) -> int:
        return self.msg_count + self.reaction_count


class EmojiBot(discord.Bot):
    def __init__(
        self,
        intents: Optional[discord.Intents],
        description: str = "A bot to get emoji's statistics in a server",
        *args,
        **kwargs,
    ):
        super().__init__(intents=intents, description=description, *args, **kwargs)

    async def on_ready(self):
        if self.user:
            activity = discord.Activity(
                type=discord.ActivityType.playing, name="statistics of emojis"
            )
            await self.change_presence(activity=activity)
            print(f"Logged in as {self.user} (ID: {self.user.id})")
        else:
            raise Exception("Failed to log in Discord server")


intents = discord.Intents.default()
intents.message_content = True
bot = EmojiBot(intents=intents)


async def scan_channel(
    channel: discord.TextChannel,
    stats: dict[str, EmojiStat],
) -> int:
    """1チャンネル分のメッセージを遡り、stats を更新する。"""
    total = 0

    async for message in channel.history(limit=None, oldest_first=True):
        # メッセージ本文中のカスタム絵文字
        for match in CUSTOM_EMOJI_PATTERN.finditer(message.content):
            name = match.group(1)
            s = stats[name]
            s.msg_count += 1
            s.channels.add(channel.id)
            s.per_channel_count[channel.id] += 1

        # リアクション
        for reaction in message.reactions:
            is_custom = hasattr(reaction.emoji, "id")
            emoji_name = (
                reaction.emoji.name
                if hasattr(reaction.emoji, "name")
                else str(reaction.emoji)
            )
            s = stats[emoji_name]
            s.is_custom = is_custom
            s.reaction_count += reaction.count
            s.channels.add(channel.id)
            s.per_channel_count[channel.id] += reaction.count

        total += 1

    return total


# ---------------------------------------------------------------------------
# グラフ生成
# ---------------------------------------------------------------------------

def _save_barh(
    labels: list[str],
    values: list[int],
    title: str,
    xlabel: str,
    path: Path,
    top_n: int = 25,
    color: str = "#5865F2",
):
    """共通の横棒グラフ保存ヘルパー。"""
    pairs = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)[:top_n]
    if not pairs:
        return
    lab, val = zip(*reversed(pairs))

    fig = go.Figure(go.Bar(
        x=list(val), y=list(lab), orientation="h",
        marker_color=color, text=list(val), textposition="outside",
    ))
    fig.update_layout(
        title=title, xaxis_title=xlabel,
        height=max(400, len(lab) * 35), width=900,
        margin=dict(l=20, r=20, t=50, b=40),
    )
    fig.write_image(str(path), scale=2)


def _save_barh_bottom(
    labels: list[str],
    values: list[int],
    title: str,
    xlabel: str,
    path: Path,
    bottom_n: int = 25,
    color: str = "#ED4245",
):
    """使用頻度が低い順の横棒グラフ保存ヘルパー。"""
    pairs = sorted(zip(labels, values), key=lambda x: x[1])[:bottom_n]
    if not pairs:
        return
    lab, val = zip(*pairs)

    fig = go.Figure(go.Bar(
        x=list(val), y=list(lab), orientation="h",
        marker_color=color, text=list(val), textposition="outside",
    ))
    fig.update_layout(
        title=title, xaxis_title=xlabel,
        height=max(400, len(lab) * 35), width=900,
        margin=dict(l=20, r=20, t=50, b=40),
    )
    fig.write_image(str(path), scale=2)


def _save_stacked_bar(
    emoji_names: list[str],
    msg_vals: list[int],
    react_vals: list[int],
    title: str,
    path: Path,
    top_n: int = 25,
):
    """本文 vs リアクションの積み上げ横棒グラフ。"""
    total = [m + r for m, r in zip(msg_vals, react_vals)]
    order = sorted(range(len(emoji_names)), key=lambda i: total[i], reverse=True)[:top_n]
    order = list(reversed(order))

    lab = [emoji_names[i] for i in order]
    mv = [msg_vals[i] for i in order]
    rv = [react_vals[i] for i in order]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=mv, y=lab, orientation="h", name="Message", marker_color="#5865F2"))
    fig.add_trace(go.Bar(x=rv, y=lab, orientation="h", name="Reaction", marker_color="#57F287"))
    fig.update_layout(
        barmode="stack", title=title, xaxis_title="Count",
        height=max(400, len(lab) * 35), width=900,
        margin=dict(l=20, r=20, t=50, b=40),
    )
    fig.write_image(str(path), scale=2)


def _save_channel_heatmap(
    stats: dict[str, EmojiStat],
    channel_map: dict[int, str],
    path: Path,
    top_emoji: int = 20,
    top_channels: int = 20,
):
    """絵文字×チャンネルのヒートマップ。"""
    sorted_emojis = sorted(stats.items(), key=lambda x: x[1].total_count, reverse=True)[:top_emoji]
    if not sorted_emojis:
        return

    all_ch_counts: Counter = Counter()
    for _, s in sorted_emojis:
        for cid, cnt in s.per_channel_count.items():
            all_ch_counts[cid] += cnt
    top_ch_ids = [cid for cid, _ in all_ch_counts.most_common(top_channels)]

    if not top_ch_ids:
        return

    emoji_labels = [name for name, _ in sorted_emojis]
    ch_labels = ["#" + channel_map.get(cid, str(cid)) for cid in top_ch_ids]

    matrix = []
    for _, s in sorted_emojis:
        row = [s.per_channel_count.get(cid, 0) for cid in top_ch_ids]
        matrix.append(row)

    fig = go.Figure(go.Heatmap(
        z=matrix, x=ch_labels, y=emoji_labels,
        colorscale="YlGnBu", texttemplate="%{z}", textfont_size=8,
    ))
    fig.update_layout(
        title="絵文字 × チャンネル 使用回数",
        height=max(400, len(emoji_labels) * 35),
        width=max(600, len(ch_labels) * 50),
        margin=dict(l=20, r=20, t=50, b=40),
        xaxis=dict(tickangle=45),
    )
    fig.write_image(str(path), scale=2)


# ---------------------------------------------------------------------------
# CSV 出力
# ---------------------------------------------------------------------------

def save_summary_csv(
    stats: dict[str, EmojiStat],
    channel_map: dict[int, str],
    path: Path,
):
    """絵文字ごとの集計 CSV。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "emoji", "total_count", "msg_count", "reaction_count",
            "channel_count", "channels",
        ])
        for name, s in sorted(stats.items(), key=lambda x: x[1].total_count, reverse=True):
            ch_names = sorted(channel_map.get(cid, str(cid)) for cid in s.channels)
            writer.writerow([
                name, s.total_count, s.msg_count, s.reaction_count,
                len(s.channels), ";".join(ch_names),
            ])


def save_per_channel_csv(
    stats: dict[str, EmojiStat],
    channel_map: dict[int, str],
    path: Path,
):
    """チャンネル×絵文字の使用回数 CSV。"""
    all_ch_ids: set = set()
    for s in stats.values():
        all_ch_ids |= set(s.per_channel_count.keys())

    ch_totals: Counter = Counter()
    for s in stats.values():
        for cid, cnt in s.per_channel_count.items():
            ch_totals[cid] += cnt
    sorted_chs = [cid for cid, _ in ch_totals.most_common()]

    sorted_emojis = sorted(stats.items(), key=lambda x: x[1].total_count, reverse=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["channel"] + [name for name, _ in sorted_emojis] + ["total"])
        for cid in sorted_chs:
            row = ["#" + channel_map.get(cid, str(cid))]
            total = 0
            for name, s in sorted_emojis:
                cnt = s.per_channel_count.get(cid, 0)
                row.append(cnt)
                total += cnt
            row.append(total)
            writer.writerow(row)


# ---------------------------------------------------------------------------
# ローカル保存 & Discord 送信
# ---------------------------------------------------------------------------

def save_all_outputs(
    stats: dict[str, EmojiStat],
    channel_map: dict[int, str],
    guild_name: str,
    scanned_channels: int,
    scanned_messages: int,
) -> Path:
    """すべてのグラフと CSV をローカルに保存し、出力ディレクトリを返す。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("output") / f"{guild_name}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sorted_items = sorted(stats.items(), key=lambda x: x[1].total_count, reverse=True)
    names = [n for n, _ in sorted_items]
    totals = [s.total_count for _, s in sorted_items]
    msg_counts = [s.msg_count for _, s in sorted_items]
    react_counts = [s.reaction_count for _, s in sorted_items]

    # 1) 使用回数 Top 25
    _save_barh(names, totals, "絵文字 使用回数 (Top 25)", "合計使用回数",
               out_dir / "01_total_count.png")

    # 2) 本文 vs リアクション 積み上げ
    _save_stacked_bar(names, msg_counts, react_counts,
                      "本文 vs リアクション (Top 25)",
                      out_dir / "02_msg_vs_reaction.png")

    # 3) 本文のみ
    msg_names = [n for n in names if stats[n].msg_count > 0]
    _save_barh(msg_names, [stats[n].msg_count for n in msg_names],
               "メッセージ本文中の絵文字 (Top 25)", "使用回数",
               out_dir / "03_message_count.png")

    # 4) リアクションのみ
    react_names = [n for n in names if stats[n].reaction_count > 0]
    _save_barh(react_names, [stats[n].reaction_count for n in react_names],
               "リアクション絵文字 (Top 25)", "使用回数",
               out_dir / "04_reaction_count.png", color="#57F287")

    # 5) チャンネル使用数
    ch_counts = [len(s.channels) for _, s in sorted_items]
    _save_barh(names, ch_counts, "絵文字が使われたチャンネル数 (Top 25)",
               "チャンネル数", out_dir / "05_channel_spread.png", color="#FEE75C")

    # 6) 使用回数 Bottom 25
    _save_barh_bottom(names, totals, "絵文字 使用回数 (Bottom 25)", "合計使用回数",
                      out_dir / "06_total_count_bottom.png")

    # 7) 本文のみ Bottom 25
    _save_barh_bottom(msg_names, [stats[n].msg_count for n in msg_names],
                      "メッセージ本文中の絵文字 (Bottom 25)", "使用回数",
                      out_dir / "07_message_count_bottom.png")

    # 8) リアクションのみ Bottom 25
    _save_barh_bottom(react_names, [stats[n].reaction_count for n in react_names],
                      "リアクション絵文字 (Bottom 25)", "使用回数",
                      out_dir / "08_reaction_count_bottom.png")

    # 9) チャンネル使用数 Bottom 25
    _save_barh_bottom(names, ch_counts, "絵文字が使われたチャンネル数 (Bottom 25)",
                      "チャンネル数", out_dir / "09_channel_spread_bottom.png", color="#FEE75C")

    # 10) チャンネル×絵文字 ヒートマップ
    _save_channel_heatmap(stats, channel_map, out_dir / "10_channel_heatmap.png")

    # --- カスタム絵文字のみ ---
    custom_stats = {n: s for n, s in stats.items() if s.is_custom}
    custom_items = [(n, s) for n, s in sorted_items if s.is_custom]
    if custom_items:
        c_names = [n for n, _ in custom_items]
        c_totals = [s.total_count for _, s in custom_items]
        c_msg = [s.msg_count for _, s in custom_items]
        c_react = [s.reaction_count for _, s in custom_items]

        # 11) カスタム絵文字 使用回数 Top 25
        _save_barh(c_names, c_totals, "カスタム絵文字 使用回数 (Top 25)", "合計使用回数",
                   out_dir / "11_custom_total_count.png")

        # 12) カスタム絵文字 本文 vs リアクション
        _save_stacked_bar(c_names, c_msg, c_react,
                          "カスタム絵文字 本文 vs リアクション (Top 25)",
                          out_dir / "12_custom_msg_vs_reaction.png")

        # 13) カスタム絵文字 本文のみ Top 25
        c_msg_names = [n for n in c_names if custom_stats[n].msg_count > 0]
        _save_barh(c_msg_names, [custom_stats[n].msg_count for n in c_msg_names],
                   "カスタム絵文字 メッセージ本文 (Top 25)", "使用回数",
                   out_dir / "13_custom_message_count.png")

        # 14) カスタム絵文字 リアクションのみ Top 25
        c_react_names = [n for n in c_names if custom_stats[n].reaction_count > 0]
        _save_barh(c_react_names, [custom_stats[n].reaction_count for n in c_react_names],
                   "カスタム絵文字 リアクション (Top 25)", "使用回数",
                   out_dir / "14_custom_reaction_count.png", color="#57F287")

        # 15) カスタム絵文字 チャンネル使用数 Top 25
        c_ch_counts = [len(s.channels) for _, s in custom_items]
        _save_barh(c_names, c_ch_counts, "カスタム絵文字が使われたチャンネル数 (Top 25)",
                   "チャンネル数", out_dir / "15_custom_channel_spread.png", color="#FEE75C")

        # 16) カスタム絵文字 使用回数 Bottom 25
        _save_barh_bottom(c_names, c_totals, "カスタム絵文字 使用回数 (Bottom 25)", "合計使用回数",
                          out_dir / "16_custom_total_count_bottom.png")

        # 17) カスタム絵文字 本文のみ Bottom 25
        _save_barh_bottom(c_msg_names, [custom_stats[n].msg_count for n in c_msg_names],
                          "カスタム絵文字 メッセージ本文 (Bottom 25)", "使用回数",
                          out_dir / "17_custom_message_count_bottom.png")

        # 18) カスタム絵文字 リアクションのみ Bottom 25
        _save_barh_bottom(c_react_names, [custom_stats[n].reaction_count for n in c_react_names],
                          "カスタム絵文字 リアクション (Bottom 25)", "使用回数",
                          out_dir / "18_custom_reaction_count_bottom.png")

        # 19) カスタム絵文字 チャンネル使用数 Bottom 25
        _save_barh_bottom(c_names, c_ch_counts, "カスタム絵文字が使われたチャンネル数 (Bottom 25)",
                          "チャンネル数", out_dir / "19_custom_channel_spread_bottom.png", color="#FEE75C")

        # 20) カスタム絵文字 チャンネル×絵文字 ヒートマップ
        _save_channel_heatmap(custom_stats, channel_map, out_dir / "20_custom_channel_heatmap.png")

    # CSV
    save_summary_csv(stats, channel_map, out_dir / "emoji_summary.csv")
    save_per_channel_csv(stats, channel_map, out_dir / "emoji_per_channel.csv")

    # サマリーテキスト
    (out_dir / "scan_info.txt").write_text(
        f"Server: {guild_name}\n"
        f"Date: {timestamp}\n"
        f"Channels scanned: {scanned_channels}\n"
        f"Messages scanned: {scanned_messages}\n"
        f"Unique emojis: {len(stats)}\n",
        encoding="utf-8",
    )

    return out_dir


@bot.slash_command(description="全チャンネルの絵文字使用統計を集計してグラフとCSVで出力します")
async def emoji_stat(ctx: discord.ApplicationContext):
    await ctx.defer()

    guild = ctx.guild
    if guild is None:
        await ctx.followup.send("このコマンドはサーバー内でのみ使用できます。")
        return

    stats: dict[str, EmojiStat] = defaultdict(EmojiStat)
    scanned_channels = 0
    scanned_messages = 0

    text_channels = [
        ch
        for ch in guild.channels
        if isinstance(ch, discord.TextChannel)
        and ch.permissions_for(guild.me).read_message_history
    ]

    channel_map = {ch.id: ch.name for ch in text_channels}

    print(f"スキャン開始: {len(text_channels)} チャンネル対象")
    status_msg = await ctx.followup.send(
        f"スキャン開始: {len(text_channels)} チャンネル対象"
    )

    for i, channel in enumerate(text_channels, 1):
        try:
            count = await scan_channel(channel, stats)
            scanned_channels += 1
            scanned_messages += count
            print(f"  [{i}/{len(text_channels)}] #{channel.name}: {count} メッセージ")
        except discord.Forbidden:
            print(f"  [{i}/{len(text_channels)}] #{channel.name}: アクセス拒否 (スキップ)")
        except Exception as e:
            print(f"  [{i}/{len(text_channels)}] #{channel.name}: エラー: {e}")

        if i % 5 == 0 or i == len(text_channels):
            try:
                await status_msg.edit(
                    content=f"スキャン中… {i}/{len(text_channels)} チャンネル "
                    f"({scanned_messages} メッセージ処理済み)"
                )
            except Exception:
                pass

        await asyncio.sleep(RATE_LIMIT_DELAY)

    # サーバーのカスタム絵文字のうち未使用のものを stats に追加
    for emoji in guild.emojis:
        if emoji.name not in stats:
            stats[emoji.name] = EmojiStat(is_custom=True)

    print(f"スキャン完了: {scanned_channels} チャンネル, {scanned_messages} メッセージ, {len(stats)} 絵文字")

    # --- ローカル保存 ---
    out_dir = save_all_outputs(
        stats, channel_map, guild.name,
        scanned_channels, scanned_messages,
    )
    print(f"Results saved to: {out_dir.resolve()}")

    # --- Discord にサマリーを送信 ---
    summary = (
        f"**スキャン完了**\n"
        f"- チャンネル数: {scanned_channels}\n"
        f"- メッセージ数: {scanned_messages}\n"
        f"- ユニーク絵文字数: {len(stats)}\n"
    )
    await ctx.followup.send(summary)

    # files = []
    # for png in sorted(out_dir.glob("*.png")):
    #     files.append(discord.File(str(png), filename=png.name))
    # for csv_file in sorted(out_dir.glob("*.csv")):
    #     files.append(discord.File(str(csv_file), filename=csv_file.name))
    #
    # # Discord の添付上限 (10ファイル) に対応して分割送信
    # await ctx.followup.send(summary, files=files[:10])
    # for chunk_start in range(10, len(files), 10):
    #     await ctx.followup.send(files=files[chunk_start:chunk_start + 10])


def main():
    parser = argparse.ArgumentParser(description="Discord emoji statistics bot")
    parser.add_argument("--token", required=True, help="Discord bot token")
    args = parser.parse_args()

    bot.run(args.token)


if __name__ == "__main__":
    main()
