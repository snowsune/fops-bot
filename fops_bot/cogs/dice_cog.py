import discord
import random
import re
import ast
from discord import app_commands
from discord.ext import commands


class DiceCog(commands.Cog, name="DiceCog"):
    def __init__(self, bot):
        self.bot = bot

    def parse_and_eval_dice_expr(self, expr: str):
        """
        Parses and evaluates a dice expression, supporting arithmetic, parentheses, and dice notation (e.g., 2d6+5, 1d20/2, 2*(1d20+5)).
        Returns a tuple: (result, breakdown_markdown, rolls_dict)
        """
        dice_pattern = re.compile(r"(\d*)d(\d+)")  # 1d20, 2d6, etc.
        rolls_dict = {}  # Store the rolls for each roll_id
        roll_id = 0  # Counter for the roll_id
        expr_work = expr  # The original expression
        roll_value = None  # The value of the roll
        steps = []  # Store the steps of the evaluation

        def roll_dice(match):  # Roll the dice and store the rolls in the rolls_dict
            nonlocal roll_id, roll_value  # Update the roll_id and roll_value
            num = int(match.group(1)) if match.group(1) else 1  # Get the number of dice
            sides = int(match.group(2))  # Get the number of sides
            rolls = [random.randint(1, sides) for _ in range(num)]  # Roll the dice
            rolls_dict[roll_id] = rolls  # Store the rolls in the rolls_dict
            val = sum(rolls)  # Sum the rolls
            if roll_value is None:
                roll_value = (
                    val if num == 1 else rolls
                )  # If there is no roll_value, set it to the value of the roll
            else:
                # If multiple dice expressions, just keep the last for display
                roll_value = val if num == 1 else rolls
            roll_id += 1
            return str(val)

        expr_no_dice = dice_pattern.sub(
            roll_dice, expr_work
        )  # Replace the dice with the rolls

        # Use ast to parse and evaluate step by step
        def eval_node(node, depth=0):
            if isinstance(node, ast.BinOp):
                left = eval_node(node.left, depth + 1)
                right = eval_node(node.right, depth + 1)
                op = node.op
                if isinstance(op, ast.Add):
                    result = left + right
                    steps.append((left, "+", right, result))
                elif isinstance(op, ast.Sub):
                    result = left - right
                    steps.append((left, "-", right, result))
                elif isinstance(op, ast.Mult):
                    result = left * right
                    steps.append((left, "*", right, result))
                elif isinstance(op, ast.Div):
                    result = left / right
                    steps.append((left, "/", right, result))
                elif isinstance(op, ast.FloorDiv):
                    result = left // right
                    steps.append((left, "//", right, result))
                elif isinstance(op, ast.Mod):
                    result = left % right
                    steps.append((left, "%", right, result))
                elif isinstance(op, ast.Pow):
                    result = left**right
                    steps.append((left, "**", right, result))
                else:
                    raise ValueError(f"Unsupported operator: {type(op)}")
                return result
            elif isinstance(node, ast.UnaryOp):
                operand = eval_node(node.operand, depth + 1)
                if isinstance(node.op, ast.USub):
                    return -operand
                elif isinstance(node.op, ast.UAdd):
                    return +operand
                else:
                    raise ValueError(f"Unsupported unary operator: {type(node.op)}")
            elif isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Constant):
                return node.value
            else:
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")

        try:
            tree = ast.parse(expr_no_dice, mode="eval")  # Parse the expression
            result = eval_node(tree.body)  # Evaluate the expression
        except Exception as e:
            raise ValueError(
                f"Invalid expression: {e}"
            )  # Raise an error if the expression is invalid

        # Build the markdown output
        md = ["# Roll Result\n"]
        if roll_value is not None:
            if isinstance(roll_value, list):
                md.append(f"**Rolls:** {roll_value}")
            else:
                md.append(f"**Roll:** {roll_value}")
        if steps:
            md.append("")
            for i, (left, op, right, res) in enumerate(steps):
                md.append(
                    f"**Modifier {i+1}/{len(steps)}** : {left} {op} {right}      -> {res}"
                )
        md.append("")
        md.append(f"**Result:** `{result}`")
        return result, "\n".join(md), rolls_dict

    @app_commands.command(name="roll")
    @app_commands.describe(
        dice="The dice expression to roll, e.g. '2d6+5', '1d20/2', '2*(1d20+5)', '3d6+1d4', '1d100-10'"
    )
    async def roll(self, ctx: discord.Interaction, dice: str):
        """
        Rolls dice using a full expression parser, supporting arithmetic, parentheses, and dice notation.

        Examples:
        - `/roll 2d6+5` - Roll 2 six-sided dice and add 5
        - `/roll 1d20` - Roll a single twenty-sided die
        - `/roll 3d6+1d4` - Roll 3 six-sided dice plus 1 four-sided die
        - `/roll 2*(1d20+5)` - Roll 1d20+5, then multiply by 2
        - `/roll 1d100-10` - Roll 1d100 and subtract 10
        """

        try:
            result, breakdown_md, rolls_dict = self.parse_and_eval_dice_expr(dice)
        except Exception as e:
            await ctx.response.send_message(f"Error: {e}", ephemeral=True)
            return
        await ctx.response.send_message(breakdown_md)


async def setup(bot):
    await bot.add_cog(DiceCog(bot))
